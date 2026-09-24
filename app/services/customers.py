"""Customer book: remembers names by phone number so repeat guests fill in instantly."""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.customer import Customer


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Keep digits (and a leading +); '98-4123 4567' → '9841234567'."""
    if not phone:
        return None
    phone = phone.strip()
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    return ("+" + digits) if phone.startswith("+") else digits


def find_customer(db: Session, restaurant_id: int, phone: Optional[str]) -> Optional[Customer]:
    phone = normalize_phone(phone)
    if not phone:
        return None
    return db.query(Customer).filter(Customer.restaurant_id == restaurant_id,
                                     Customer.phone == phone).first()


def upsert_customer(db: Session, restaurant_id: int, name: Optional[str], phone: Optional[str],
                    spent: float = 0.0, visit: bool = False) -> Optional[Customer]:
    phone = normalize_phone(phone)
    if not phone:
        return None
    name = (name or "").strip()
    c = find_customer(db, restaurant_id, phone)
    if c is None:
        c = Customer(restaurant_id=restaurant_id, name=name or phone, phone=phone,
                     total_visits=0, total_spent=0.0, loyalty_points=0)
        db.add(c)
    elif name:
        c.name = name
    if visit:
        c.total_visits = (c.total_visits or 0) + 1
    if spent:
        c.total_spent = round((c.total_spent or 0.0) + spent, 2)
    return c
