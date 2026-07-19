from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.table import RestaurantTable
from app.models.order import Order
from app.models.bill import Bill
from app.models.user import User
from app.routes.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/tables", tags=["tables"])


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


# --- Endpoints ---

@router.get("")
def list_tables(db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    q = db.query(RestaurantTable)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    return q.order_by(RestaurantTable.floor, RestaurantTable.table_number).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_table(body: TableCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
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
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    table = q.first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
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
    db.delete(table)
    db.commit()


@router.get("/floor/{floor_name}")
def tables_by_floor(floor_name: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    q = db.query(RestaurantTable).filter(RestaurantTable.floor == floor_name)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    return q.order_by(RestaurantTable.table_number).all()


@router.get("/{table_id}/active-order")
def get_active_order(table_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Return the currently active order for a table, or null if none."""
    q = db.query(RestaurantTable).filter(RestaurantTable.id == table_id)
    if current_user.restaurant_id:
        q = q.filter(RestaurantTable.restaurant_id == current_user.restaurant_id)
    if not q.first():
        raise HTTPException(status_code=404, detail="Table not found")

    oq = db.query(Order).filter(Order.table_id == table_id, Order.status == "active")
    if current_user.restaurant_id:
        oq = oq.filter(Order.restaurant_id == current_user.restaurant_id)
    order = oq.first()
    if not order:
        return None

    from app.routes.orders import _order_detail
    return _order_detail(order, db)


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
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bills
    ]
