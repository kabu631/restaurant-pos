"""
Order operations shared by the orders, tables, reservations and billing routes:
loading orders with their items, adding items, sending KOTs, and keeping
table status in step with the orders on it.
"""
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.restaurant import Restaurant
from app.models.table import RestaurantTable
from app.models.user import User
from app.services import printer as printer_svc
from app.services.billing_calc import apply_totals, compute_totals, order_lines
from app.services.restaurant_settings import (TaxConfig, as_bool, get_setting,
                                              printer_path, tax_config)
from app.utils import nepal

# Items the kitchen still has to act on
KITCHEN_STATUSES = ("sent", "preparing", "ready")


def restaurant_id_of(user: User) -> int:
    """Restaurant of the acting user; superadmin has none and cannot run a POS."""
    if not user.restaurant_id:
        raise HTTPException(status_code=400,
                            detail="Log in with a restaurant account to use the POS.")
    return user.restaurant_id


def lock_restaurant(db: Session, restaurant_id: int) -> None:
    """Serialise ticket/bill numbering per restaurant (row lock; no-op on SQLite,
    which serialises writers anyway).  Take it before touching other rows."""
    db.query(Restaurant.id).filter(Restaurant.id == restaurant_id).with_for_update().first()


def get_order(db: Session, order_id: int, user: User) -> Order:
    q = db.query(Order).filter(Order.id == order_id)
    if user.restaurant_id:
        q = q.filter(Order.restaurant_id == user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def require_active(order: Order) -> None:
    if order.status != "active":
        raise HTTPException(status_code=400,
                            detail=f"Order #{order.id} is {order.status} and can no longer be changed")


def _station(category: Optional[Category]) -> str:
    return (category.station if category and category.station else "kitchen")


def _item_rows(db: Session, order_id: int, status: Optional[str] = None):
    q = (
        db.query(OrderItem, MenuItem, Category)
        .outerjoin(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .outerjoin(Category, Category.id == MenuItem.category_id)
        .filter(OrderItem.order_id == order_id)
    )
    if status:
        q = q.filter(OrderItem.kot_status == status)
    return q.order_by(OrderItem.id).all()


def order_detail(db: Session, order: Order, cfg: Optional[TaxConfig] = None) -> dict:
    items = []
    subtotal = 0.0
    counts = {"pending": 0, "in_kitchen": 0, "ready": 0, "served": 0, "void": 0}
    for oi, mi, cat in _item_rows(db, order.id):
        line_total = round(oi.quantity * oi.unit_price, 2)
        items.append({
            "id": oi.id,
            "menu_item_id": oi.menu_item_id,
            "name": mi.name if mi else "Unknown",
            "quantity": oi.quantity,
            "unit_price": oi.unit_price,
            "line_total": line_total,
            "notes": oi.notes,
            "kot_status": oi.kot_status,
            "kot_number": oi.kot_number,
            "kot_sent_at": nepal.iso(oi.kot_sent_at),
            "station": _station(cat),
        })
        if oi.kot_status == "void":
            counts["void"] += 1
            continue
        subtotal += line_total
        if oi.kot_status == "pending":
            counts["pending"] += 1
        elif oi.kot_status == "ready":
            counts["ready"] += 1
        elif oi.kot_status == "served":
            counts["served"] += 1
        else:
            counts["in_kitchen"] += 1

    table_number = None
    if order.table_id:
        tbl = db.get(RestaurantTable, order.table_id)
        table_number = tbl.table_number if tbl else None
    waiter = db.get(User, order.waiter_id) if order.waiter_id else None
    bill = (db.query(Bill)
              .filter(Bill.order_id == order.id, Bill.payment_status != "void")
              .order_by(Bill.id.desc()).first())

    cfg = cfg or tax_config(db, order.restaurant_id)
    estimate = compute_totals(order_lines(db, order.id), None, 0.0, True, cfg)

    return {
        "id": order.id,
        "order_type": order.order_type,
        "status": order.status,
        "table_id": order.table_id,
        "table_number": table_number,
        "guests": order.guests,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "delivery_address": order.delivery_address,
        "notes": order.notes,
        "waiter_id": order.waiter_id,
        "waiter_name": waiter.full_name if waiter else None,
        "subtotal": round(subtotal, 2),
        "estimated_total": estimate["grand_total"],
        "counts": counts,
        "items": items,
        "bill": ({"id": bill.id, "bill_number": bill.bill_number,
                  "payment_status": bill.payment_status, "grand_total": bill.grand_total}
                 if bill else None),
        "created_at": nepal.iso(order.created_at),
        "updated_at": nepal.iso(order.updated_at),
    }


def _clean_note(note: Optional[str]) -> Optional[str]:
    note = (note or "").strip()
    return note[:200] or None


def add_items(db: Session, order: Order, items: Iterable) -> list[OrderItem]:
    """Add menu items (objects with menu_item_id, quantity, notes) as pending lines.

    A line merges into an existing unsent line of the same dish only when the
    kitchen notes match, so "Momo — no spice" never swallows a plain "Momo".
    """
    require_active(order)
    items = list(items)
    if not items:
        return []
    ids = {i.menu_item_id for i in items}
    menu = {
        m.id: m for m in db.query(MenuItem).filter(
            MenuItem.id.in_(ids), MenuItem.restaurant_id == order.restaurant_id
        ).all()
    }
    added = []
    for req in items:
        mi = menu.get(req.menu_item_id)
        if not mi:
            raise HTTPException(status_code=404, detail=f"Menu item {req.menu_item_id} not found")
        if not mi.is_available:
            raise HTTPException(status_code=400, detail=f"{mi.name} is not available right now")
        if req.quantity < 1 or req.quantity > 999:
            raise HTTPException(status_code=400, detail="Quantity must be between 1 and 999")
        note = _clean_note(req.notes)
        existing = next((
            oi for oi in db.query(OrderItem).filter(
                OrderItem.order_id == order.id,
                OrderItem.menu_item_id == mi.id,
                OrderItem.kot_status == "pending",
            ).all()
            if _clean_note(oi.notes) == note
        ), None)
        if existing:
            existing.quantity += req.quantity
            added.append(existing)
        else:
            oi = OrderItem(order_id=order.id, menu_item_id=mi.id, quantity=req.quantity,
                           unit_price=mi.price, notes=note, kot_status="pending")
            db.add(oi)
            db.flush()  # visible to the merge lookup for the next line (autoflush is off)
            added.append(oi)
    db.flush()
    return added


def next_kot_number(db: Session, restaurant_id: int) -> int:
    """Daily KOT sequence per restaurant: #1 is the first ticket after midnight NPT."""
    lock_restaurant(db, restaurant_id)
    start, end = nepal.day_bounds(nepal.today())
    current = (
        db.query(func.max(OrderItem.kot_number))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.restaurant_id == restaurant_id,
                OrderItem.kot_sent_at >= start, OrderItem.kot_sent_at < end)
        .scalar()
    )
    return (current or 0) + 1


def send_kot(db: Session, order: Order) -> Optional[dict]:
    """Fire all pending items: kitchen/bar items get a ticket number, items from
    'no ticket' categories are marked served straight away.  None if nothing pending."""
    rows = _item_rows(db, order.id, status="pending")
    if not rows:
        return None
    now = nepal.now()
    ticket_rows = [(oi, mi, cat) for oi, mi, cat in rows if _station(cat) != "none"]
    direct_rows = [(oi, mi, cat) for oi, mi, cat in rows if _station(cat) == "none"]

    kot_number = next_kot_number(db, order.restaurant_id) if ticket_rows else None
    for oi, _, _ in ticket_rows:
        oi.kot_status = "sent"
        oi.kot_number = kot_number
        oi.kot_sent_at = now
    for oi, _, _ in direct_rows:
        oi.kot_status = "served"
        oi.kot_sent_at = now

    return {
        "order_id": order.id,
        "kot_number": kot_number,
        "items_sent": len(ticket_rows),
        "items_direct": len(direct_rows),
        "stations": sorted({_station(cat) for _, _, cat in ticket_rows}),
        "items": [
            {"name": mi.name if mi else "Unknown", "quantity": oi.quantity,
             "notes": oi.notes, "station": _station(cat)}
            for oi, mi, cat in ticket_rows
        ],
    }


def dispatch_kot_print(db: Session, order: Order, kot: dict) -> dict:
    """Decide how a new ticket gets printed and tell the UI via kot["print_mode"]:
    'thermal' = the server is printing it, 'browser' = open the KOT print page,
    None = auto-print is off (the UI offers a Print button instead)."""
    kot["print_mode"] = None
    if not kot.get("kot_number"):
        return kot
    if not as_bool(get_setting(db, order.restaurant_id, "auto_print_kot"), False):
        return kot
    path = printer_path(db, order.restaurant_id)
    if not path:
        kot["print_mode"] = "browser"
        return kot

    kot["print_mode"] = "thermal"
    tbl = db.get(RestaurantTable, order.table_id) if order.table_id else None
    waiter = db.get(User, order.waiter_id) if order.waiter_id else None
    for station in kot["stations"]:  # one slip per station: kitchen and bar
        printer_svc.print_async(printer_svc.print_kot, {
            "kot_number": kot["kot_number"],
            "order_id": order.id,
            "order_type": order.order_type,
            "table_number": tbl.table_number if tbl else None,
            "waiter_name": waiter.full_name if waiter else None,
            "station": station,
            "time": nepal.now().strftime("%H:%M"),
            "items": [i for i in kot["items"] if i["station"] == station],
        }, path)
    return kot


def void_all_items(db: Session, order: Order) -> int:
    """Void every live item (used when an order is cancelled) — clears its KDS tickets."""
    n = 0
    for oi in db.query(OrderItem).filter(OrderItem.order_id == order.id,
                                         OrderItem.kot_status != "void").all():
        oi.kot_status = "void"
        n += 1
    return n


def release_table_id(db: Session, table_id: Optional[int], leaving_order_id: int) -> None:
    """Free a table unless an active order other than the leaving one still sits on it."""
    if not table_id:
        return
    other = db.query(Order.id).filter(
        Order.table_id == table_id,
        Order.status == "active",
        Order.id != leaving_order_id,
    ).first()
    tbl = db.get(RestaurantTable, table_id)
    if tbl and not other:
        tbl.status = "free"


def release_table(db: Session, order: Order) -> None:
    """Free the order's table once the order is paid, cancelled or moved."""
    release_table_id(db, order.table_id, order.id)


def active_order_for_table(db: Session, table_id: int) -> Optional[Order]:
    return (db.query(Order)
              .filter(Order.table_id == table_id, Order.status == "active")
              .order_by(Order.id).first())


def refresh_unpaid_bill(db: Session, order: Order) -> Optional[Bill]:
    """Keep an issued-but-unpaid bill in step after the order's items change."""
    bill = db.query(Bill).filter(Bill.order_id == order.id,
                                 Bill.payment_status == "unpaid").first()
    if not bill:
        return None
    totals = compute_totals(order_lines(db, order.id), bill.discount_type,
                            bill.discount_value or 0.0, (bill.service_charge or 0) > 0,
                            tax_config(db, order.restaurant_id))
    apply_totals(bill, totals)
    return bill
