import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone

from app.database import get_db, db_transaction
from app.models.order import Order, OrderItem

_log = logging.getLogger(__name__)
from app.models.menu import MenuItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])

VALID_STATUSES = {"active", "completed", "cancelled"}
VALID_KOT_STATUSES = {"pending", "sent", "preparing", "ready", "served"}
VALID_ORDER_TYPES = {"dine_in", "takeaway", "delivery"}


# --- Schemas ---

class OrderCreate(BaseModel):
    order_type: str = "dine_in"
    table_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    notes: Optional[str] = None

class OrderItemAdd(BaseModel):
    menu_item_id: int
    quantity: int = 1
    notes: Optional[str] = None

class OrderItemUpdate(BaseModel):
    quantity: Optional[int] = None
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str

class KOTStatusUpdate(BaseModel):
    kot_status: str


# --- Helpers ---

def _order_detail(order: Order, db: Session) -> dict:
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    item_list = []
    subtotal = 0.0
    for oi in items:
        mi = db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first()
        line = {
            "id": oi.id,
            "menu_item_id": oi.menu_item_id,
            "name": mi.name if mi else "Unknown",
            "quantity": oi.quantity,
            "unit_price": oi.unit_price,
            "line_total": round(oi.quantity * oi.unit_price, 2),
            "notes": oi.notes,
            "kot_status": oi.kot_status,
            "kot_number": oi.kot_number,
        }
        item_list.append(line)
        subtotal += line["line_total"]

    table_number = None
    if order.table_id:
        tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if tbl:
            table_number = tbl.table_number

    return {
        "id": order.id,
        "order_type": order.order_type,
        "status": order.status,
        "table_id": order.table_id,
        "table_number": table_number,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "notes": order.notes,
        "subtotal": round(subtotal, 2),
        "items": item_list,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


# --- Endpoints ---

@router.get("")
def list_orders(
    status_filter: Optional[str] = None,
    table_id: Optional[int] = None,
    order_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Order)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    if status_filter:
        q = q.filter(Order.status == status_filter)
    if table_id:
        q = q.filter(Order.table_id == table_id)
    if order_type:
        q = q.filter(Order.order_type == order_type)
    orders = q.order_by(Order.created_at.desc()).all()
    return [_order_detail(o, db) for o in orders]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    if body.order_type not in VALID_ORDER_TYPES:
        raise HTTPException(status_code=400, detail=f"order_type must be one of {VALID_ORDER_TYPES}")

    tbl = None
    if body.table_id:
        q = db.query(RestaurantTable).filter(RestaurantTable.id == body.table_id)
        if current_user.restaurant_id:
            q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
        tbl = q.first()
        if not tbl:
            raise HTTPException(status_code=404, detail="Table not found")
        if tbl.status == "occupied":
            raise HTTPException(status_code=409, detail="Table is already occupied")

    with db_transaction(db):
        if tbl:
            tbl.status = "occupied"
        order = Order(
            restaurant_id=current_user.restaurant_id,
            order_type=body.order_type,
            table_id=body.table_id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            notes=body.notes,
            waiter_id=current_user.id,
            status="active",
        )
        db.add(order)
        db.commit()
        db.refresh(order)

    return _order_detail(order, db)


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    q = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_detail(order, db)


@router.patch("/{order_id}/status")
def update_order_status(order_id: int, body: OrderStatusUpdate,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    q = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = body.status
    if body.status in ("completed", "cancelled") and order.table_id:
        tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if tbl:
            tbl.status = "free"
    db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/{order_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(order_id: int, body: OrderItemAdd, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    q = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "active":
        raise HTTPException(status_code=400, detail="Cannot add items to a non-active order")

    mq = db.query(MenuItem).filter(MenuItem.id == body.menu_item_id)
    if current_user.restaurant_id:
        mq = mq.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    mi = mq.first()
    if not mi:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if not mi.is_available:
        raise HTTPException(status_code=400, detail="Menu item is not available")

    # Merge with existing item if present and not yet sent to kitchen
    existing = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.menu_item_id == body.menu_item_id,
        OrderItem.kot_status == "pending",
    ).first()

    if existing:
        existing.quantity += body.quantity
        db.commit()
        db.refresh(existing)
        oi = existing
    else:
        oi = OrderItem(
            order_id=order_id,
            menu_item_id=body.menu_item_id,
            quantity=body.quantity,
            unit_price=mi.price,
            notes=body.notes,
            kot_status="pending",
        )
        db.add(oi)
        db.commit()
        db.refresh(oi)

    return {
        "id": oi.id,
        "menu_item_id": oi.menu_item_id,
        "name": mi.name,
        "quantity": oi.quantity,
        "unit_price": oi.unit_price,
        "line_total": round(oi.quantity * oi.unit_price, 2),
        "notes": oi.notes,
        "kot_status": oi.kot_status,
    }


@router.put("/{order_id}/items/{oi_id}")
def update_item(order_id: int, oi_id: int, body: OrderItemUpdate,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    oq = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    if not oq.first():
        raise HTTPException(status_code=404, detail="Order not found")
    oi = db.query(OrderItem).filter(
        OrderItem.id == oi_id, OrderItem.order_id == order_id
    ).first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    if body.quantity is not None:
        if body.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        oi.quantity = body.quantity
    if body.notes is not None:
        oi.notes = body.notes
    db.commit()
    db.refresh(oi)
    return {"id": oi.id, "quantity": oi.quantity, "notes": oi.notes,
            "line_total": round(oi.quantity * oi.unit_price, 2)}


@router.delete("/{order_id}/items/{oi_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(order_id: int, oi_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    oq = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    if not oq.first():
        raise HTTPException(status_code=404, detail="Order not found")
    oi = db.query(OrderItem).filter(
        OrderItem.id == oi_id, OrderItem.order_id == order_id
    ).first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    db.delete(oi)
    db.commit()


@router.post("/{order_id}/kot")
def send_kot(order_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    q = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    pending_items = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.kot_status == "pending",
    ).all()

    if not pending_items:
        raise HTTPException(status_code=400, detail="No pending items to send to kitchen")

    max_kot = max((i.kot_number or 0 for i in
                   db.query(OrderItem).filter(OrderItem.order_id == order_id).all()), default=0)
    kot_num = max_kot + 1
    now = datetime.now(timezone.utc)

    with db_transaction(db):
        for oi in pending_items:
            oi.kot_status = "sent"
            oi.kot_number = kot_num
            oi.kot_sent_at = now
        db.commit()

    return {
        "order_id": order_id,
        "kot_number": kot_num,
        "items_sent": len(pending_items),
        "items": [
            {"name": db.query(MenuItem).filter(MenuItem.id == i.menu_item_id).first().name,
             "quantity": i.quantity, "notes": i.notes}
            for i in pending_items
        ],
    }


@router.patch("/{order_id}/items/{oi_id}/kot-status")
def update_kot_status(order_id: int, oi_id: int, body: KOTStatusUpdate,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    if body.kot_status not in VALID_KOT_STATUSES:
        raise HTTPException(status_code=400, detail=f"kot_status must be one of {VALID_KOT_STATUSES}")
    oq = db.query(Order).filter(Order.id == order_id)
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    if not oq.first():
        raise HTTPException(status_code=404, detail="Order not found")
    oi = db.query(OrderItem).filter(
        OrderItem.id == oi_id, OrderItem.order_id == order_id
    ).first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    oi.kot_status = body.kot_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status}
