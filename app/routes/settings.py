"""
Settings API — admin can update their restaurant profile and per-restaurant
key/value settings (receipt footer, tax, payment methods, printer, ...).
"""
import base64
import socket

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.config import HOST, PORT
from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.user import User
from app.routes.auth import get_current_user, require_admin
from app.services.restaurant_settings import (
    DEFAULT_PAYMENT_METHODS, DEFAULT_QUICK_NOTES, DEFAULT_RESERVATION_HOLD_MIN,
    PAYMENT_METHODS, QR_METHODS, as_bool, enabled_payment_methods, get_setting,
    get_settings, quick_notes, set_setting, tax_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys that admins are allowed to read/write → default shown when unset
ALLOWED_KEYS = {
    "receipt_footer": "",           # Text printed at the bottom of every receipt
    "receipt_note": "",             # Optional note printed above item list
    "thermal_printer_path": "",     # COM3 / 192.168.1.50 — overrides .env per restaurant
    "auto_print_kot": "false",      # "true" → print every KOT as soon as it is sent
    "currency_symbol": "NPR",
    "vat_enabled": "true",          # false for PAN-only (non-VAT) restaurants
    "vat_rate": "13",
    "service_charge_enabled": "true",
    "service_charge_rate": "10",
    "payment_methods": DEFAULT_PAYMENT_METHODS,   # comma list of enabled tenders
    "quick_notes": DEFAULT_QUICK_NOTES,           # one-tap kitchen notes on the order screen
    "reservation_hold_minutes": str(DEFAULT_RESERVATION_HOLD_MIN),
}
_BOOL_KEYS = {"auto_print_kot", "vat_enabled", "service_charge_enabled"}
_NUMBER_KEYS = {"vat_rate": (0, 100), "service_charge_rate": (0, 100),
                "reservation_hold_minutes": (0, 1440)}
_MAX_QR_BYTES = 512 * 1024
_QR_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,",
                "data:image/jpg;base64,", "data:image/webp;base64,")


# --- Schemas ---

class RestaurantProfile(BaseModel):
    name:       Optional[str] = None
    phone:      Optional[str] = None
    address:    Optional[str] = None
    vat_number: Optional[str] = None

class SettingUpsert(BaseModel):
    key:   str
    value: str

class PaymentQR(BaseModel):
    image: Optional[str] = None   # data URL; null removes it


# --- Helpers ---

def _clean_value(key: str, value) -> str:
    value = "" if value is None else str(value).strip()
    if key in _BOOL_KEYS:
        return "true" if as_bool(value, False) else "false"
    if key in _NUMBER_KEYS and value != "":
        lo, hi = _NUMBER_KEYS[key]
        try:
            number = float(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{key} must be a number")
        if not lo <= number <= hi:
            raise HTTPException(status_code=400, detail=f"{key} must be between {lo} and {hi}")
        return f"{number:g}"
    if key == "payment_methods":
        keys = [k.strip() for k in value.split(",") if k.strip()]
        unknown = [k for k in keys if k not in PAYMENT_METHODS]
        if unknown or not keys:
            raise HTTPException(status_code=400,
                                detail=f"payment_methods must be a comma list of {sorted(PAYMENT_METHODS)}")
        return ",".join(k for k in PAYMENT_METHODS if k in keys)
    return value[:2000]


def _restaurant_profile(r: Restaurant, db: Session) -> dict:
    stored = get_settings(db, r.id, ALLOWED_KEYS)
    return {
        "id":         r.id,
        "name":       r.name,
        "slug":       r.slug,
        "phone":      r.phone or "",
        "address":    r.address or "",
        "vat_number": r.vat_number or "",
        "is_active":  r.is_active,
        "settings":   {key: stored.get(key, default) for key, default in ALLOWED_KEYS.items()},
        "payment_method_labels": PAYMENT_METHODS,
        "payment_qr": {m: get_setting(db, r.id, f"qr_image_{m}") for m in QR_METHODS},  # data URLs
    }


def _own_restaurant(db: Session, user: User) -> Restaurant:
    if not user.restaurant_id:
        raise HTTPException(status_code=400, detail="Superadmin has no restaurant profile")
    r = db.query(Restaurant).filter(Restaurant.id == user.restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return r


def _lan_addresses() -> list[str]:
    """Best guess at this PC's addresses on the local network."""
    addrs = []
    try:  # the interface used for outbound traffic — no packets are actually sent
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            addrs.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in addrs and not ip.startswith("127."):
                addrs.append(ip)
    except OSError:
        pass
    return addrs


# --- Endpoints ---

@router.get("")
def get_settings_all(current_user: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """Return restaurant profile + all editable settings."""
    return _restaurant_profile(_own_restaurant(db, current_user), db)


@router.get("/pos")
def pos_settings(current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Read-only config every staff screen needs (no secrets)."""
    rid = current_user.restaurant_id
    if not rid:
        return {"quick_notes": [], "tax": tax_config(db, None).as_dict(), "payment_methods": [],
                "currency": "NPR", "restaurant_name": None}
    r = db.query(Restaurant).filter(Restaurant.id == rid).first()
    return {
        "restaurant_name": r.name if r else None,
        "quick_notes": quick_notes(db, rid),
        "tax": tax_config(db, rid).as_dict(),
        "payment_methods": enabled_payment_methods(db, rid),
        "currency": get_setting(db, rid, "currency_symbol", "NPR"),
        "auto_print_kot": as_bool(get_setting(db, rid, "auto_print_kot"), False),
    }


@router.put("/profile")
def update_profile(body: RestaurantProfile,
                   current_user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """Update restaurant name, phone, address, VAT number."""
    r = _own_restaurant(db, current_user)
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
    _own_restaurant(db, current_user)
    if body.key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown setting key. Allowed: {sorted(ALLOWED_KEYS)}")
    value = _clean_value(body.key, body.value)
    set_setting(db, current_user.restaurant_id, body.key, value)
    db.commit()
    return {"key": body.key, "value": value}


@router.put("/bulk")
def bulk_update(body: dict,
                current_user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    """Update multiple settings + profile fields in one call.
    Accepted body: { profile: {...}, settings: {key: value, ...} }
    """
    r = _own_restaurant(db, current_user)

    profile = body.get("profile") or {}
    if "name" in profile and not str(profile["name"] or "").strip():
        raise HTTPException(status_code=400, detail="Restaurant name is required")
    for field in ("name", "phone", "address", "vat_number"):
        if field in profile and profile[field] is not None:
            setattr(r, field, str(profile[field]).strip())

    settings = body.get("settings") or {}
    unknown = [k for k in settings if k not in ALLOWED_KEYS]
    if unknown:
        raise HTTPException(status_code=400,
                            detail=f"Unknown setting keys: {unknown}")
    cleaned = {key: _clean_value(key, value) for key, value in settings.items()}
    for key, value in cleaned.items():
        set_setting(db, current_user.restaurant_id, key, value)

    db.commit()
    db.refresh(r)
    return _restaurant_profile(r, db)


@router.put("/payment-qr/{method}")
def set_payment_qr(method: str, body: PaymentQR,
                   current_user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """Upload (or remove) the restaurant's static merchant QR for FonePay / eSewa /
    Khalti / bank, shown to the customer on the payment screen."""
    _own_restaurant(db, current_user)
    if method not in QR_METHODS:
        raise HTTPException(status_code=400, detail=f"QR images are supported for {list(QR_METHODS)}")
    image = (body.image or "").strip()
    if image:
        if not image.startswith(_QR_PREFIXES):
            raise HTTPException(status_code=400, detail="Upload a PNG, JPG or WebP image")
        try:
            raw = base64.b64decode(image.split(",", 1)[1], validate=True)
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="The image could not be read")
        if len(raw) > _MAX_QR_BYTES:
            raise HTTPException(status_code=400, detail="Image is too large (max 512 KB)")
    set_setting(db, current_user.restaurant_id, f"qr_image_{method}", image or None)
    db.commit()
    return {"method": method, "has_qr": bool(image)}


@router.get("/network")
def network_info(current_user: User = Depends(require_admin)):
    """How other devices (waiter phones, kitchen tablet) can reach this POS."""
    lan_enabled = HOST not in ("127.0.0.1", "localhost", "::1")
    return {
        "host": HOST,
        "port": PORT,
        "lan_enabled": lan_enabled,
        "urls": [f"http://{ip}:{PORT}" for ip in _lan_addresses()] if lan_enabled else [],
    }
