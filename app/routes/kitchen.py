from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.services import audit
from app.services.permissions import require_perm
from app.routes.auth import get_current_user
from app.services.order_ops import KITCHEN_STATUSES
from app.utils import nepal

router = APIRouter(prefix="/api/kitchen", tags=["kitchen"])

BUMP_FLOW = {"sent": "preparing", "preparing": "ready", "ready": "served"}
VALID_STATIONS = {"kitchen", "bar"}


class ItemStatusUpdate(BaseModel):
    kot_status: str


def _station_expr():
    return func.coalesce(Category.station, "kitchen")


def _kitchen_rows(db: Session, restaurant_id: Optional[int], station: Optional[str] = None,
                  statuses=KITCHEN_STATUSES):
    q = (
        db.query(OrderItem, Order, MenuItem, _station_expr())
        .join(Order, Order.id == OrderItem.order_id)
        .outerjoin(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .outerjoin(Category, Category.id == MenuItem.category_id)
        .filter(OrderItem.kot_status.in_(statuses), Order.status != "cancelled")
    )
    if restaurant_id:
        q = q.filter(Order.restaurant_id == restaurant_id)
    if station:
        if station not in VALID_STATIONS:
            raise HTTPException(status_code=400, detail="station must be 'kitchen' or 'bar'")
        q = q.filter(_station_expr() == station)
    return q.order_by(OrderItem.kot_sent_at, OrderItem.id).all()


def _build_tickets(db: Session, restaurant_id: Optional[int] = None,
                   station: Optional[str] = None) -> list:
    """
    Return all active KOT tickets grouped by (order_id, kot_number), oldest first.
    Each ticket lists its items with status sent/preparing/ready.
    """
    rows = _kitchen_rows(db, restaurant_id, station)
    table_ids = {o.table_id for _, o, _, _ in rows if o.table_id}
    waiter_ids = {o.waiter_id for _, o, _, _ in rows if o.waiter_id}
    tables = {t.id: t.table_number for t in
              db.query(RestaurantTable).filter(RestaurantTable.id.in_(table_ids)).all()} if table_ids else {}
    waiters = {u.id: u.full_name for u in
               db.query(User).filter(User.id.in_(waiter_ids)).all()} if waiter_ids else {}
    now = nepal.now()

    tickets: dict[tuple, dict] = {}
    for oi, order, mi, item_station in rows:
        key = (oi.order_id, oi.kot_number or 0)
        ticket = tickets.get(key)
        if ticket is None:
            sent_at = oi.kot_sent_at
            ticket = tickets[key] = {
                "order_id": oi.order_id,
                "kot_number": oi.kot_number,
                "table_number": tables.get(order.table_id),
                "order_type": order.order_type,
                "customer_name": order.customer_name,
                "order_notes": order.notes,
                "guests": order.guests,
                "waiter_name": waiters.get(order.waiter_id),
                "sent_at": nepal.iso(sent_at),
                # Server-side age: tablets in the kitchen often have the wrong clock
                "age_sec": max(0, int((now - sent_at).total_seconds())) if sent_at else 0,
                "items": [],
                "stations": [],
                "all_ready": True,
            }
        ticket["items"].append({
            "id": oi.id,
            "name": mi.name if mi else "Unknown",
            "quantity": oi.quantity,
            "notes": oi.notes,
            "kot_status": oi.kot_status,
            "station": item_station,
        })
        if item_station not in ticket["stations"]:
            ticket["stations"].append(item_station)
        if oi.kot_status != "ready":
            ticket["all_ready"] = False

    return list(tickets.values())


def _get_item(db: Session, oi_id: int, user: User) -> OrderItem:
    q = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.id == oi_id)
    )
    if user.restaurant_id:
        q = q.filter(Order.restaurant_id == user.restaurant_id)
    oi = q.first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    return oi


@router.get("/tickets")
def get_tickets(station: Optional[str] = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return _build_tickets(db, restaurant_id=current_user.restaurant_id, station=station)


@router.get("/tickets/count")
def ticket_count(db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Lightweight poll endpoint — returns count of active kitchen items."""
    q = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.kot_status.in_(KITCHEN_STATUSES), Order.status != "cancelled")
    )
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    return {"active_items": q.count()}


@router.get("/ready")
def ready_to_serve(db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """Dishes the kitchen has finished, grouped by order — the waiters' pick-up list."""
    rows = _kitchen_rows(db, current_user.restaurant_id, statuses=("ready",))
    table_ids = {o.table_id for _, o, _, _ in rows if o.table_id}
    tables = {t.id: t.table_number for t in
              db.query(RestaurantTable).filter(RestaurantTable.id.in_(table_ids)).all()} if table_ids else {}
    orders: dict[int, dict] = {}
    for oi, order, mi, _ in rows:
        entry = orders.setdefault(order.id, {
            "order_id": order.id,
            "table_number": tables.get(order.table_id),
            "order_type": order.order_type,
            "customer_name": order.customer_name,
            "items": [],
        })
        entry["items"].append({"id": oi.id, "name": mi.name if mi else "Unknown",
                               "quantity": oi.quantity})
    # Count dishes (quantities), matching the "N ready" badges on the floor plan
    return {"ready_items": sum(oi.quantity for oi, _, _, _ in rows), "orders": list(orders.values())}


@router.patch("/items/{oi_id}/bump")
def bump_item(oi_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(require_perm("kitchen.manage"))):
    """Advance item through sent → preparing → ready → served."""
    oi = _get_item(db, oi_id, current_user)
    next_status = BUMP_FLOW.get(oi.kot_status)
    if not next_status:
        raise HTTPException(status_code=400,
                            detail=f"Item status '{oi.kot_status}' cannot be bumped")
    previous = oi.kot_status
    oi.kot_status = next_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status, "previous": previous}


@router.patch("/tickets/{order_id}/{kot_number}/advance")
def advance_ticket(order_id: int, kot_number: int, station: Optional[str] = None,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_perm("kitchen.manage"))):
    """One tap for the whole ticket: Start (sent → preparing), Ready (→ ready), Done (→ served).
    With ?station= only that station's items on the ticket move."""
    oq = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    if not oq.first():
        raise HTTPException(status_code=404, detail="Order not found")
    items = [oi for oi, _, _, item_station in
             _kitchen_rows(db, current_user.restaurant_id, station)
             if oi.order_id == order_id and oi.kot_number == kot_number]
    if not items:
        raise HTTPException(status_code=400, detail="Nothing left on this ticket")

    statuses = {oi.kot_status for oi in items}
    if "sent" in statuses:
        moving, to = ("sent",), "preparing"
    elif "preparing" in statuses:
        moving, to = ("preparing",), "ready"
    else:
        moving, to = ("ready",), "served"
    changed = []
    for oi in items:
        if oi.kot_status in moving:
            changed.append({"id": oi.id, "previous": oi.kot_status})
            oi.kot_status = to
    if to == "preparing":
        audit.record(db, current_user, "ACCEPT_KOT", "orders", order_id, {"kot": kot_number})
    db.commit()
    return {"kot_status": to, "changed": changed}


@router.patch("/tickets/{order_id}/{kot_number}/bump-all")
def bump_all_ready(order_id: int, kot_number: int,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_perm("kitchen.manage"))):
    """Mark all ready items on a ticket as served (ticket complete)."""
    oq = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    if not oq.first():
        raise HTTPException(status_code=404, detail="Order not found")
    items = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.kot_number == kot_number,
        OrderItem.kot_status == "ready",
    ).all()
    if not items:
        raise HTTPException(status_code=400, detail="No ready items on this ticket")
    for oi in items:
        oi.kot_status = "served"
    db.commit()
    return {"served": len(items)}


@router.patch("/items/{oi_id}/status")
def set_item_status(oi_id: int, body: ItemStatusUpdate,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_perm("kitchen.manage"))):
    """Set an item's KOT status directly (for corrections and undo)."""
    valid = {"sent", "preparing", "ready", "served"}
    if body.kot_status not in valid:
        raise HTTPException(status_code=400, detail=f"kot_status must be one of {valid}")
    oi = _get_item(db, oi_id, current_user)
    if oi.kot_status in ("pending", "void"):
        raise HTTPException(status_code=400, detail=f"Item is {oi.kot_status} and not in the kitchen")
    oi.kot_status = body.kot_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status}
