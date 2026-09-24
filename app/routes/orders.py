import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db, db_transaction
from app.models.bill import Bill
from app.models.menu import MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.routes.auth import get_current_user
from app.services import audit
from app.services import order_ops as ops
from app.services.customers import upsert_customer
from app.services.restaurant_settings import tax_config

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])

VALID_STATUSES = {"active", "completed", "cancelled"}
VALID_KOT_STATUSES = {"pending", "sent", "preparing", "ready", "served"}
VALID_ORDER_TYPES = {"dine_in", "takeaway", "delivery"}

# House rule: once food has gone to the kitchen it can't be cancelled — it must be billed.
KITCHEN_LOCKED = "This item has already gone to the kitchen and can't be cancelled."
ORDER_LOCKED = ("Food for this order has already gone to the kitchen, so the order can't be "
                "cancelled. Create the bill to close it.")


# --- Schemas ---

class OrderItemAdd(BaseModel):
    menu_item_id: int
    quantity: int = 1
    notes: Optional[str] = None

class OrderCreate(BaseModel):
    order_type: str = "dine_in"
    table_id: Optional[int] = None
    guests: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    items: List[OrderItemAdd] = []
    send_kot: bool = False

class OrderUpdate(BaseModel):
    guests: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = None

class OrderItemsBulk(BaseModel):
    items: List[OrderItemAdd] = []
    send_kot: bool = False

class OrderItemUpdate(BaseModel):
    quantity: Optional[int] = None
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str

class KOTStatusUpdate(BaseModel):
    kot_status: str

class ReasonBody(BaseModel):
    reason: Optional[str] = None

class TransferBody(BaseModel):
    table_id: int


# --- Helpers ---

def _check_guests(guests: Optional[int]):
    if guests is not None and not 1 <= guests <= 200:
        raise HTTPException(status_code=400, detail="Guests must be between 1 and 200")


def _get_item(db: Session, order: Order, oi_id: int) -> OrderItem:
    oi = db.query(OrderItem).filter(OrderItem.id == oi_id,
                                    OrderItem.order_id == order.id).first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")
    return oi


def _sent_to_kitchen(db: Session, order: Order) -> bool:
    """True once any dish has left the "not sent" stage (sent, cooking, ready or served)."""
    return db.query(OrderItem.id).filter(
        OrderItem.order_id == order.id,
        OrderItem.kot_status.notin_(("pending", "void")),
    ).first() is not None


def _line_out(db: Session, oi: OrderItem) -> dict:
    mi = db.get(MenuItem, oi.menu_item_id)
    return {
        "id": oi.id,
        "menu_item_id": oi.menu_item_id,
        "name": mi.name if mi else "Unknown",
        "quantity": oi.quantity,
        "unit_price": oi.unit_price,
        "line_total": round(oi.quantity * oi.unit_price, 2),
        "notes": oi.notes,
        "kot_status": oi.kot_status,
    }


# --- Endpoints ---

@router.get("")
def list_orders(
    status_filter: Optional[str] = None,
    table_id: Optional[int] = None,
    order_type: Optional[str] = None,
    limit: int = 200,
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
    orders = q.order_by(Order.created_at.desc()).limit(max(1, min(limit, 1000))).all()
    cfg = tax_config(db, current_user.restaurant_id)
    return [ops.order_detail(db, o, cfg) for o in orders]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Open an order — optionally with its first items and KOT in the same call."""
    rid = ops.restaurant_id_of(current_user)
    if body.order_type not in VALID_ORDER_TYPES:
        raise HTTPException(status_code=400, detail=f"order_type must be one of {VALID_ORDER_TYPES}")
    _check_guests(body.guests)

    tbl = None
    if body.table_id:
        tbl = db.query(RestaurantTable).filter(RestaurantTable.id == body.table_id,
                                               RestaurantTable.restaurant_id == rid).first()
        if not tbl:
            raise HTTPException(status_code=404, detail="Table not found")
        existing = ops.active_order_for_table(db, tbl.id)
        if existing:
            raise HTTPException(status_code=409,
                                detail=f"Table {tbl.table_number} already has an open order (#{existing.id})",
                                headers={"X-Order-Id": str(existing.id)})

    with db_transaction(db):
        if body.send_kot:
            ops.lock_restaurant(db, rid)
        order = Order(
            restaurant_id=rid,
            order_type=body.order_type,
            table_id=tbl.id if tbl else None,
            guests=body.guests,
            customer_name=(body.customer_name or "").strip() or None,
            customer_phone=(body.customer_phone or "").strip() or None,
            delivery_address=(body.delivery_address or "").strip() or None,
            notes=(body.notes or "").strip() or None,
            waiter_id=current_user.id,
            status="active",
        )
        db.add(order)
        db.flush()
        if tbl:
            tbl.status = "occupied"
        ops.add_items(db, order, body.items)
        kot = ops.send_kot(db, order) if body.send_kot else None
        if order.customer_phone:
            upsert_customer(db, rid, order.customer_name, order.customer_phone)
        db.commit()
        db.refresh(order)

    detail = ops.order_detail(db, order)
    if kot:
        detail["kot"] = ops.dispatch_kot_print(db, order, kot)
    return detail


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    return ops.order_detail(db, ops.get_order(db, order_id, current_user))


@router.patch("/{order_id}")
def update_order(order_id: int, body: OrderUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Edit guests, customer details, delivery address or order notes."""
    order = ops.get_order(db, order_id, current_user)
    ops.require_active(order)
    _check_guests(body.guests)
    for field, value in body.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(order, field, value)
    if order.customer_phone:
        upsert_customer(db, order.restaurant_id, order.customer_name, order.customer_phone)
    db.commit()
    return ops.order_detail(db, order)


@router.patch("/{order_id}/status")
def update_order_status(order_id: int, body: OrderStatusUpdate,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    order = ops.get_order(db, order_id, current_user)
    if body.status == "cancelled":
        return cancel_order(order_id, ReasonBody(), db, current_user)
    if body.status == "completed":
        # Closing an order with food on it happens by paying the bill, never by status alone
        paid = db.query(Bill.id).filter(Bill.order_id == order.id,
                                        Bill.payment_status == "paid").first()
        has_items = db.query(OrderItem.id).filter(OrderItem.order_id == order.id,
                                                  OrderItem.kot_status != "void").first()
        if has_items and not paid:
            raise HTTPException(status_code=400, detail="Create the bill and take payment to close this order")
    order.status = body.status
    if body.status == "completed":
        ops.release_table(db, order)
    db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, body: ReasonBody, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Cancel an order that the kitchen hasn't received anything for (entered by mistake,
    guests left before ordering).  Once food has gone to the kitchen it must be billed."""
    order = ops.get_order(db, order_id, current_user)
    ops.require_active(order)
    if _sent_to_kitchen(db, order):
        raise HTTPException(status_code=409, detail=ORDER_LOCKED)
    open_bill = db.query(Bill).filter(Bill.order_id == order.id,
                                      Bill.payment_status == "unpaid").first()
    if open_bill:
        raise HTTPException(status_code=409,
                            detail=f"Bill {open_bill.bill_number} is open for this order — void the bill first")
    with db_transaction(db):
        voided = ops.void_all_items(db, order)
        order.status = "cancelled"
        ops.release_table(db, order)
        audit.record(db, current_user, "CANCEL_ORDER", "orders", order.id,
                     {"items_voided": voided}, reason=body.reason)
        db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/{order_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(order_id: int, body: OrderItemAdd, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    order = ops.get_order(db, order_id, current_user)
    with db_transaction(db):
        (oi,) = ops.add_items(db, order, [body])
        ops.refresh_unpaid_bill(db, order)
        db.commit()
        db.refresh(oi)
    return _line_out(db, oi)


@router.post("/{order_id}/items/bulk")
def add_items_bulk(order_id: int, body: OrderItemsBulk, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """Add several items at once and optionally fire them to the kitchen — one atomic call."""
    order = ops.get_order(db, order_id, current_user)
    ops.require_active(order)
    with db_transaction(db):
        if body.send_kot:
            ops.lock_restaurant(db, order.restaurant_id)
        ops.add_items(db, order, body.items)
        kot = ops.send_kot(db, order) if body.send_kot else None
        if body.send_kot and not kot:
            raise HTTPException(status_code=400, detail="No pending items to send to kitchen")
        ops.refresh_unpaid_bill(db, order)
        db.commit()
    detail = ops.order_detail(db, order)
    if kot:
        detail["kot"] = ops.dispatch_kot_print(db, order, kot)
    return detail


@router.put("/{order_id}/items/{oi_id}")
def update_item(order_id: int, oi_id: int, body: OrderItemUpdate,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    order = ops.get_order(db, order_id, current_user)
    oi = _get_item(db, order, oi_id)
    if oi.kot_status != "pending":
        raise HTTPException(status_code=400, detail=KITCHEN_LOCKED)
    if body.quantity is not None:
        if not 1 <= body.quantity <= 999:
            raise HTTPException(status_code=400, detail="Quantity must be between 1 and 999")
        oi.quantity = body.quantity
    if body.notes is not None:
        oi.notes = body.notes.strip()[:200] or None
    ops.refresh_unpaid_bill(db, order)
    db.commit()
    db.refresh(oi)
    return {"id": oi.id, "quantity": oi.quantity, "notes": oi.notes,
            "line_total": round(oi.quantity * oi.unit_price, 2)}


@router.delete("/{order_id}/items/{oi_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(order_id: int, oi_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    order = ops.get_order(db, order_id, current_user)
    oi = _get_item(db, order, oi_id)
    if oi.kot_status != "pending":
        raise HTTPException(status_code=400, detail=KITCHEN_LOCKED)
    db.delete(oi)
    db.flush()
    ops.refresh_unpaid_bill(db, order)
    db.commit()


@router.post("/{order_id}/kot")
def send_kot(order_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    order = ops.get_order(db, order_id, current_user)
    with db_transaction(db):
        ops.lock_restaurant(db, order.restaurant_id)
        kot = ops.send_kot(db, order)
        if not kot:
            raise HTTPException(status_code=400, detail="No pending items to send to kitchen")
        db.commit()
    return ops.dispatch_kot_print(db, order, kot)


@router.post("/{order_id}/serve-ready")
def serve_ready(order_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """Waiter picked up everything the kitchen marked ready."""
    order = ops.get_order(db, order_id, current_user)
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id,
                                       OrderItem.kot_status == "ready").all()
    for oi in items:
        oi.kot_status = "served"
    db.commit()
    return {"order_id": order.id, "served": len(items)}


@router.post("/{order_id}/transfer")
def transfer_order(order_id: int, body: TransferBody, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """Move an open order to another free table."""
    order = ops.get_order(db, order_id, current_user)
    ops.require_active(order)
    target = db.query(RestaurantTable).filter(
        RestaurantTable.id == body.table_id,
        RestaurantTable.restaurant_id == order.restaurant_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Table not found")
    if target.id == order.table_id:
        raise HTTPException(status_code=400, detail="The order is already on that table")
    busy = ops.active_order_for_table(db, target.id)
    if busy:
        raise HTTPException(status_code=409,
                            detail=f"Table {target.table_number} already has an open order (#{busy.id})")
    with db_transaction(db):
        old_table_id = order.table_id
        order.table_id = target.id
        order.order_type = "dine_in"
        target.status = "occupied"
        db.flush()
        ops.release_table_id(db, old_table_id, order.id)
        audit.record(db, current_user, "TRANSFER_ORDER", "orders", order.id,
                     {"from_table_id": old_table_id, "to_table_id": target.id})
        db.commit()
    return ops.order_detail(db, order)


@router.patch("/{order_id}/items/{oi_id}/kot-status")
def update_kot_status(order_id: int, oi_id: int, body: KOTStatusUpdate,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    if body.kot_status not in VALID_KOT_STATUSES:
        raise HTTPException(status_code=400, detail=f"kot_status must be one of {VALID_KOT_STATUSES}")
    order = ops.get_order(db, order_id, current_user)
    oi = _get_item(db, order, oi_id)
    if oi.kot_status == "void":
        raise HTTPException(status_code=400, detail="Item is void")
    if body.kot_status == "pending" and oi.kot_status != "pending":
        raise HTTPException(status_code=400, detail=KITCHEN_LOCKED)   # no "un-sending" to delete it
    if body.kot_status != "pending" and oi.kot_status == "pending":
        raise HTTPException(status_code=400, detail="Use Send to kitchen to send this item")
    oi.kot_status = body.kot_status
    db.commit()
    return {"id": oi.id, "kot_status": oi.kot_status}
