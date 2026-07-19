"""
Settings API — admin can update their restaurant profile and per-restaurant
key/value settings (receipt footer, thermal printer path, etc.).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.inventory import AppSettings
from app.models.user import User
from app.routes.auth import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys that admins are allowed to read/write
ALLOWED_KEYS = {
    "receipt_footer",       # Text printed at the bottom of every receipt
    "receipt_note",         # Optional note printed above item list
    "thermal_printer_path", # COM3 / /dev/usb/lp0 — overrides .env per restaurant
    "auto_print_kot",       # "true" / "false"
    "currency_symbol",      # Default "NPR"
}


# --- Schemas ---

class RestaurantProfile(BaseModel):
    name:       Optional[str] = None
    phone:      Optional[str] = None
    address:    Optional[str] = None
    vat_number: Optional[str] = None

class SettingUpsert(BaseModel):
    key:   str
    value: str


# --- Helpers ---

def _get_setting(db: Session, restaurant_id: int, key: str) -> Optional[str]:
    row = db.query(AppSettings).filter(
        AppSettings.restaurant_id == restaurant_id,
        AppSettings.key == key,
    ).first()
    return row.value if row else None


def _set_setting(db: Session, restaurant_id: int, key: str, value: str):
    row = db.query(AppSettings).filter(
        AppSettings.restaurant_id == restaurant_id,
        AppSettings.key == key,
    ).first()
    if row:
        row.value = value
    else:
        db.add(AppSettings(restaurant_id=restaurant_id, key=key, value=value))


def _restaurant_profile(r: Restaurant, db: Session) -> dict:
    rid = r.id
    return {
        "id":         r.id,
        "name":       r.name,
        "slug":       r.slug,
        "phone":      r.phone or "",
        "address":    r.address or "",
        "vat_number": r.vat_number or "",
        "is_active":  r.is_active,
        "settings": {
            key: (_get_setting(db, rid, key) or "")
            for key in ALLOWED_KEYS
        },
    }


# --- Endpoints ---

@router.get("")
def get_settings(current_user: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """Return restaurant profile + all editable settings."""
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Superadmin has no restaurant profile")
    r = db.query(Restaurant).filter(
        Restaurant.id == current_user.restaurant_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return _restaurant_profile(r, db)


@router.put("/profile")
def update_profile(body: RestaurantProfile,
                   current_user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """Update restaurant name, phone, address, VAT number."""
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Superadmin has no restaurant profile")
    r = db.query(Restaurant).filter(
        Restaurant.id == current_user.restaurant_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _restaurant_profile(r, db)


@router.put("/key")
def upsert_setting(body: SettingUpsert,
                   current_user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """Create or update a single setting key."""
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Superadmin has no restaurant profile")
    if body.key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown setting key. Allowed: {sorted(ALLOWED_KEYS)}")
    _set_setting(db, current_user.restaurant_id, body.key, body.value)
    db.commit()
    return {"key": body.key, "value": body.value}


@router.put("/bulk")
def bulk_update(body: dict,
                current_user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    """Update multiple settings + profile fields in one call.
    Accepted body: { profile: {...}, settings: {key: value, ...} }
    """
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Superadmin has no restaurant profile")

    r = db.query(Restaurant).filter(
        Restaurant.id == current_user.restaurant_id
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    profile = body.get("profile", {})
    for field in ("name", "phone", "address", "vat_number"):
        if field in profile and profile[field] is not None:
            setattr(r, field, profile[field])

    settings = body.get("settings", {})
    unknown = [k for k in settings if k not in ALLOWED_KEYS]
    if unknown:
        raise HTTPException(status_code=400,
                            detail=f"Unknown setting keys: {unknown}")
    for key, value in settings.items():
        _set_setting(db, current_user.restaurant_id, key, str(value))

    db.commit()
    db.refresh(r)
    return _restaurant_profile(r, db)
