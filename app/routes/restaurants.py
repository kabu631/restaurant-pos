from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import re

from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.user import User
from app.routes.auth import require_superadmin
from app.utils.security import hash_password

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,30}[a-z0-9]$")


# --- Schemas ---

class RestaurantRegister(BaseModel):
    restaurant_name: str
    restaurant_code: str        # slug — letters, numbers, hyphens
    phone: Optional[str] = None
    address: Optional[str] = None
    vat_number: Optional[str] = None
    admin_username: str
    admin_password: str
    admin_full_name: str

class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    vat_number: Optional[str] = None


# --- Helpers ---

def _restaurant_dict(r: Restaurant, db: Session) -> dict:
    user_count = db.query(User).filter(User.restaurant_id == r.id).count()
    return {
        "id": r.id,
        "name": r.name,
        "slug": r.slug,
        "phone": r.phone,
        "address": r.address,
        "vat_number": r.vat_number,
        "is_active": r.is_active,
        "user_count": user_count,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_restaurant(body: RestaurantRegister, db: Session = Depends(get_db)):
    """Public endpoint — new clients self-register their restaurant."""
    slug = body.restaurant_code.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=400,
            detail="Restaurant code must be 3–32 characters: lowercase letters, numbers, hyphens only. Cannot start or end with a hyphen."
        )

    if db.query(Restaurant).filter(Restaurant.slug == slug).first():
        raise HTTPException(status_code=409, detail="Restaurant code already taken. Choose a different one.")

    if len(body.admin_password) < 6:
        raise HTTPException(status_code=400, detail="Admin password must be at least 6 characters.")

    restaurant = Restaurant(
        name=body.restaurant_name.strip(),
        slug=slug,
        phone=body.phone,
        address=body.address,
        vat_number=body.vat_number,
        is_active=True,
    )
    db.add(restaurant)
    db.flush()  # get restaurant.id before committing

    admin = User(
        restaurant_id=restaurant.id,
        username=body.admin_username.strip().lower(),
        password_hash=hash_password(body.admin_password),
        full_name=body.admin_full_name.strip(),
        role="admin",
        is_active=True,
        pin=None,
    )
    db.add(admin)
    db.commit()
    db.refresh(restaurant)

    return {
        "message": "Restaurant registered successfully.",
        "restaurant_code": restaurant.slug,
        "restaurant_name": restaurant.name,
        "admin_username": admin.username,
    }


@router.get("")
def list_restaurants(db: Session = Depends(get_db),
                     _=Depends(require_superadmin)):
    """Superadmin only — list all restaurants."""
    restaurants = db.query(Restaurant).order_by(Restaurant.created_at.desc()).all()
    return [_restaurant_dict(r, db) for r in restaurants]


@router.get("/{restaurant_id}")
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db),
                   _=Depends(require_superadmin)):
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return _restaurant_dict(r, db)


@router.patch("/{restaurant_id}/toggle")
def toggle_restaurant(restaurant_id: int, db: Session = Depends(get_db),
                      _=Depends(require_superadmin)):
    """Superadmin only — activate or deactivate a restaurant account."""
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    r.is_active = not r.is_active
    db.commit()
    return {"id": r.id, "slug": r.slug, "is_active": r.is_active}


@router.patch("/{restaurant_id}")
def update_restaurant(restaurant_id: int, body: RestaurantUpdate,
                      db: Session = Depends(get_db), _=Depends(require_superadmin)):
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _restaurant_dict(r, db)
