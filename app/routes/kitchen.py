from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.menu import MenuItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/kitchen", tags=["kitchen"])

# Statuses visible in the kitchen (everything except pending/served)
KITCHEN_STATUSES = {"sent", "preparing", "ready"}
BUMP_FLOW = {"sent": "preparing", "preparing": "ready", "ready": "served"}


class ItemStatusUpdate(BaseModel):
    kot_status: str


def _build_tickets(db: Session, restaurant_id: Optional[int] = None) -> list:
    """
    Return all active KOT tickets grouped by (order_id, kot_number).
    Each ticket lists its items with status sent/preparing/ready.
    """
    q = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.kot_status.in_(KITCHEN_STATUSES))
    )
    if restaurant_id:
        q = q.filter(Order.restaurant_id == restaurant_id)
    active_items = q.order_by(OrderItem.kot_sent_at).all()

    tickets: dict[tuple, dict] = {}
    for oi in active_items:
        key = (oi.order_id, oi.kot_number or 0)
        if key not in tickets:
            order = db.query(Order).filter(Order.id == oi.order_id).first()
            tbl_num = None
            if order and order.table_id:
                tbl = db.query(RestaurantTable).filter(
                    RestaurantTable.id == order.table_id
                ).first()
                tbl_num = tbl.table_number if tbl else None

            tickets[key] = {
                "order_id": oi.order_id,
                "kot_number": oi.kot_number,
                "table_number": tbl_num,
                "order_type": order.order_type if order else "unknown",
                "customer_name": order.customer_name if order else None,
                "order_notes": order.notes if order else None,
                "sent_at": oi.kot_sent_at.isoformat() if oi.kot_sent_at else None,
                "items": [],
                "all_ready": True,
            }

        mi = db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first()
        tickets[key]["items"].append({
            "id": oi.id,
            "name": mi.name if mi else "Unknown",
            "quantity": oi.quantity,
            "notes": oi.notes,
            "kot_status": oi.kot_status,
        })
        if oi.kot_status != "ready":
            tickets[key]["all_ready"] = False

    return list(tickets.values())


@router.get("/tickets")
def get_tickets(db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return _build_tickets(db, restaurant_id=current_user.restaurant_id)


@router.get("/tickets/count")
def ticket_count(db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Lightweight poll endpoint — returns count of active kitchen items."""
    q = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.kot_status.in_(KITCHEN_STATUSES))
    )
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    return {"active_items": q.count()}


@router.patch("/items/{oi_id}/bump")
def bump_item(oi_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    """Advance item through sent → preparing → ready → served."""
    oi = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.id == oi_id)
    )
    if current_user.restaurant_id:
        oi = oi.filter(Order.restaurant_id == current_user.restaurant_id)
    oi = oi.first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    next_status = BUMP_FLOW.get(oi.kot_status)
    if not next_status:
        raise HTTPException(status_code=400,
                            detail=f"Item status '{oi.kot_status}' cannot be bumped")
    oi.kot_status = next_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status}


@router.patch("/tickets/{order_id}/{kot_number}/bump-all")
def bump_all_ready(order_id: int, kot_number: int,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
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
                    current_user: User = Depends(get_current_user)):
    """Set an item's KOT status directly (for corrections)."""
    valid = {"sent", "preparing", "ready", "served"}
    if body.kot_status not in valid:
        raise HTTPException(status_code=400, detail=f"kot_status must be one of {valid}")
    oi = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(OrderItem.id == oi_id)
    )
    if current_user.restaurant_id:
        oi = oi.filter(Order.restaurant_id == current_user.restaurant_id)
    oi = oi.first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    oi.kot_status = body.kot_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status}
