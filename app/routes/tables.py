import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.bill import Bill
from app.models.menu import MenuItem
from app.models.order import Order, OrderItem
from app.models.reservation import Reservation
from app.models.table import RestaurantTable
from app.models.user import User
from app.routes.auth import get_current_user, require_admin
from app.services import order_ops as ops
from app.services.billing_calc import compute_totals
from app.services.restaurant_settings import (DEFAULT_RESERVATION_HOLD_MIN, get_setting,
                                              tax_config)
from app.utils import nepal

router = APIRouter(prefix="/api/tables", tags=["tables"])

_FLOOR_ORDER = ["ground", "first", "second", "third", "rooftop", "terrace", "garden"]
# A booked table shows as reserved from hold-window before the booking until this long after
_RESERVATION_GRACE = timedelta(minutes=30)


# --- Schemas ---

class TableCreate(BaseModel):
    table_number: str
    capacity: int
    floor: Optional[str] = "Ground"
    pos_x: int = 0
    pos_y: int = 0

class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    floor: Optional[str] = None
    pos_x: Optional[int] = None
    pos_y: Optional[int] = None

class TableStatusUpdate(BaseModel):
    status: str  # free / occupied / reserved


# --- Helpers ---

def natural_key(text: str) -> list:
    """'T2' sorts before 'T10'."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", text or "")]


def _floor_key(floor: Optional[str]):
    name = (floor or "Ground").strip().lower()
    return (_FLOOR_ORDER.index(name) if name in _FLOOR_ORDER else len(_FLOOR_ORDER), name)


def _validate_table(capacity: Optional[int], table_number: Optional[str]):
    if capacity is not None and not 1 <= capacity <= 100:
        raise HTTPException(status_code=400, detail="Capacity must be between 1 and 100")
    if table_number is not None and not table_number.strip():
        raise HTTPException(status_code=400, detail="Table number is required")


def reservation_brief(r: Reservation) -> dict:
    return {
        "id": r.id,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "party_size": r.party_size,
        "reserved_for": nepal.iso(r.reserved_for),
        "notes": r.notes,
    }


# --- Endpoints ---

@router.get("")
def list_tables(db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    q = db.query(RestaurantTable)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    tables = q.all()
    return sorted(tables, key=lambda t: (_floor_key(t.floor), natural_key(t.table_number)))


@router.get("/overview")
def tables_overview(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Everything the floor plan needs in one call: tables with their live order
    and upcoming booking, plus open takeaway/delivery orders."""
    rid = ops.restaurant_id_of(current_user)
    now = nepal.now()
    cfg = tax_config(db, rid)

    tables = sorted(
        db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == rid).all(),
        key=lambda t: (_floor_key(t.floor), natural_key(t.table_number)),
    )
    orders = (db.query(Order)
                .filter(Order.restaurant_id == rid, Order.status == "active")
                .order_by(Order.created_at).all())
    order_ids = [o.id for o in orders]

    # Per-order money and kitchen progress in a single grouped query
    agg: dict[int, dict] = {oid: {"vatable": 0.0, "other": 0.0, "items": 0, "pending": 0,
                                  "in_kitchen": 0, "ready": 0, "awaiting_accept": 0,
                                  "accepted": 0} for oid in order_ids}
    if order_ids:
        rows = (
            db.query(OrderItem.order_id, OrderItem.kot_status, MenuItem.is_vat_applicable,
                     func.sum(OrderItem.quantity * OrderItem.unit_price),
                     func.sum(OrderItem.quantity))
            .outerjoin(MenuItem, MenuItem.id == OrderItem.menu_item_id)
            .filter(OrderItem.order_id.in_(order_ids), OrderItem.kot_status != "void")
            .group_by(OrderItem.order_id, OrderItem.kot_status, MenuItem.is_vat_applicable)
            .all()
        )
        for order_id, kot_status, vatable, amount, qty in rows:
            a = agg[order_id]
            a["vatable" if vatable is not False else "other"] += float(amount or 0)
            a["items"] += int(qty or 0)
            if kot_status == "pending":
                a["pending"] += int(qty or 0)
            elif kot_status == "ready":
                a["ready"] += int(qty or 0)
            elif kot_status in ("sent", "preparing"):
                a["in_kitchen"] += int(qty or 0)
            if kot_status == "sent":                          # kitchen hasn't accepted yet
                a["awaiting_accept"] += int(qty or 0)
            elif kot_status in ("preparing", "ready", "served"):
                a["accepted"] += int(qty or 0)                # incl. drinks served straight away
    billed = {b.order_id for b in db.query(Bill.order_id).filter(
        Bill.order_id.in_(order_ids), Bill.payment_status == "unpaid").all()} if order_ids else set()
    waiter_ids = {o.waiter_id for o in orders if o.waiter_id}
    waiters = {u.id: u.full_name for u in
               db.query(User).filter(User.id.in_(waiter_ids)).all()} if waiter_ids else {}

    def summary(o: Order) -> dict:
        a = agg[o.id]
        lines = [{"line_total": a["vatable"], "is_vat_applicable": True},
                 {"line_total": a["other"], "is_vat_applicable": False}]
        created = nepal.to_npt(o.created_at)
        return {
            "id": o.id,
            "order_type": o.order_type,
            "table_id": o.table_id,
            "guests": o.guests,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "waiter_name": waiters.get(o.waiter_id),
            "created_at": nepal.iso(o.created_at),
            "minutes_open": max(0, int((now - created).total_seconds() // 60)) if created else 0,
            "subtotal": round(a["vatable"] + a["other"], 2),
            "estimated_total": compute_totals(lines, None, 0.0, True, cfg)["grand_total"],
            "items": a["items"],
            "pending": a["pending"],
            "in_kitchen": a["in_kitchen"],
            "ready": a["ready"],
            "awaiting_accept": a["awaiting_accept"],
            # Once the kitchen accepts (or drinks are served), the table's total is the cashier's to bill
            "ready_to_bill": a["accepted"] > 0,
            "bill_open": o.id in billed,
        }

    table_orders: dict[int, Order] = {}
    open_orders = []
    for o in orders:
        if o.table_id and o.table_id not in table_orders:
            table_orders[o.table_id] = o
        elif not o.table_id:
            open_orders.append(summary(o))

    hold = timedelta(minutes=int(float(get_setting(db, rid, "reservation_hold_minutes",
                                                   str(DEFAULT_RESERVATION_HOLD_MIN)))))
    upcoming = (db.query(Reservation)
                  .filter(Reservation.restaurant_id == rid,
                          Reservation.status == "booked",
                          Reservation.table_id.isnot(None),
                          Reservation.reserved_for <= now + hold,
                          Reservation.reserved_for >= now - _RESERVATION_GRACE)
                  .order_by(Reservation.reserved_for).all())
    held: dict[int, Reservation] = {}
    for r in upcoming:
        held.setdefault(r.table_id, r)

    out, floors, counts = [], [], {"free": 0, "occupied": 0, "reserved": 0}
    for t in tables:
        floor = t.floor or "Ground"
        if floor not in floors:
            floors.append(floor)
        order = table_orders.get(t.id)
        booking = held.get(t.id)
        if order:
            state = "occupied"
        elif booking or t.status == "reserved":
            state = "reserved"
        else:
            state = "free"
        counts[state] += 1
        out.append({
            "id": t.id,
            "table_number": t.table_number,
            "capacity": t.capacity,
            "floor": floor,
            "status": state,
            "order": summary(order) if order else None,
            "reservation": reservation_brief(booking) if booking else None,
        })

    start, end = nepal.day_bounds(now.date())
    bookings_today = db.query(Reservation).filter(
        Reservation.restaurant_id == rid,
        Reservation.status == "booked",
        Reservation.reserved_for >= start,
        Reservation.reserved_for < end,
    ).count()

    return {
        "now": nepal.iso(now),
        "floors": floors,
        "counts": counts,
        "tables": out,
        "open_orders": open_orders,
        "bookings_today": bookings_today,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_table(body: TableCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    _validate_table(body.capacity, body.table_number)
    body.table_number = body.table_number.strip()
    q = db.query(RestaurantTable).filter(RestaurantTable.table_number == body.table_number)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    if q.first():
        raise HTTPException(status_code=409, detail="Table number already exists")
    table = RestaurantTable(**body.model_dump(), restaurant_id=current_user.restaurant_id)
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


@router.put("/{table_id}")
def update_table(table_id: int, body: TableUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    _validate_table(body.capacity, body.table_number)
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    table = q.first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    if body.table_number and body.table_number.strip() != table.table_number:
        dup = db.query(RestaurantTable).filter(
            RestaurantTable.restaurant_id == table.restaurant_id,
            RestaurantTable.table_number == body.table_number.strip(),
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail="Table number already exists")
        body.table_number = body.table_number.strip()
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(table, field, value)
    db.commit()
    db.refresh(table)
    return table


@router.patch("/{table_id}/status")
def update_table_status(table_id: int, body: TableStatusUpdate,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    if body.status not in ("free", "occupied", "reserved"):
        raise HTTPException(status_code=400, detail="Status must be free, occupied, or reserved")
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    table = q.first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    busy = ops.active_order_for_table(db, table.id)
    if busy and body.status != "occupied":
        raise HTTPException(status_code=409,
                            detail=f"Table {table.table_number} has an open order (#{busy.id}) — pay or cancel it first")
    table.status = body.status
    db.commit()
    return {"id": table.id, "table_number": table.table_number, "status": table.status}


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table(table_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    table = q.first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    if db.query(Order.id).filter(Order.table_id == table.id).first():
        raise HTTPException(status_code=409,
                            detail="This table has order history and can't be deleted — rename it instead")
    if db.query(Reservation.id).filter(Reservation.table_id == table.id,
                                       Reservation.status == "booked").first():
        raise HTTPException(status_code=409, detail="This table has upcoming bookings — move them first")
    db.delete(table)
    db.commit()


@router.get("/floor/{floor_name}")
def tables_by_floor(floor_name: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    q = db.query(RestaurantTable).filter(RestaurantTable.floor == floor_name)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    return sorted(q.all(), key=lambda t: natural_key(t.table_number))


@router.get("/{table_id}/active-order")
def get_active_order(table_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Return the currently active order for a table, or null if none."""
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    if not q.first():
        raise HTTPException(status_code=404, detail="Table not found")
    order = ops.active_order_for_table(db, table_id)
    return ops.order_detail(db, order) if order else None


@router.get("/{table_id}/outstanding-bills")
def get_outstanding_bills(table_id: int, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """Return all unpaid bills for active/completed orders on this table."""
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    if not q.first():
        raise HTTPException(status_code=404, detail="Table not found")

    oq = db.query(Order).filter(
        Order.table_id == table_id,
        Order.status.in_(["active", "completed"]),
    )
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    order_ids = [o.id for o in oq.all()]

    if not order_ids:
        return []

    bills = db.query(Bill).filter(
        Bill.order_id.in_(order_ids),
        Bill.payment_status == "unpaid",
    ).all()

    return [
        {
            "id": b.id,
            "bill_number": b.bill_number,
            "order_id": b.order_id,
            "grand_total": b.grand_total,
            "payment_status": b.payment_status,
            "created_at": nepal.iso(b.created_at),
        }
        for b in bills
    ]
