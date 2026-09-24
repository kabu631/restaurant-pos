from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.customer import Customer
from app.models.user import User
from app.routes.auth import get_current_user
from app.services import order_ops as ops
from app.services.customers import find_customer, normalize_phone

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _out(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone,
            "total_visits": c.total_visits or 0, "total_spent": c.total_spent or 0.0}


@router.get("/lookup")
def lookup(phone: str, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    """Exact phone match → the saved guest, or null."""
    c = find_customer(db, ops.restaurant_id_of(current_user), phone)
    return _out(c) if c else None


@router.get("")
def search(q: Optional[str] = None, limit: int = 8, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    """Type-ahead by phone prefix or name."""
    rid = ops.restaurant_id_of(current_user)
    query = db.query(Customer).filter(Customer.restaurant_id == rid)
    text = (q or "").strip()
    if text:
        digits = normalize_phone(text)
        conds = [Customer.name.ilike(f"%{text}%")]
        if digits:
            conds.append(Customer.phone.like(f"{digits}%"))
        query = query.filter(or_(*conds))
    rows = query.order_by(Customer.total_visits.desc(), Customer.name).limit(max(1, min(limit, 50))).all()
    return [_out(c) for c in rows]
