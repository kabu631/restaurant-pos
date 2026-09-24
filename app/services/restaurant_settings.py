"""
Per-restaurant settings stored as AppSettings key/value rows, with typed
accessors.  Anything not set falls back to the defaults in app.config.
"""
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.config import (SERVICE_CHARGE_ENABLED, SERVICE_CHARGE_RATE,
                        THERMAL_PRINTER_PATH, VAT_RATE)
from app.models.inventory import AppSettings

# key → label shown on the payment screen (order = display order)
PAYMENT_METHODS = {
    "cash":   "Cash",
    "card":   "Card",
    "qr":     "FonePay QR",
    "esewa":  "eSewa",
    "khalti": "Khalti",
    "bank":   "Bank Transfer",
}
DEFAULT_PAYMENT_METHODS = "cash,card,qr,esewa,khalti"
# Methods where the restaurant can upload its static merchant QR for customers to scan
QR_METHODS = ("qr", "esewa", "khalti", "bank")

DEFAULT_QUICK_NOTES = "No spice,Less spicy,Extra spicy,No onion,No garlic,Less oil,Pack separately"
DEFAULT_RESERVATION_HOLD_MIN = 60


def get_setting(db: Session, restaurant_id: int, key: str,
                default: Optional[str] = None) -> Optional[str]:
    row = db.query(AppSettings).filter(
        AppSettings.restaurant_id == restaurant_id,
        AppSettings.key == key,
    ).first()
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def get_settings(db: Session, restaurant_id: int, keys: Iterable[str]) -> dict:
    """Fetch several keys in one query → {key: value}; missing keys are omitted."""
    rows = db.query(AppSettings).filter(
        AppSettings.restaurant_id == restaurant_id,
        AppSettings.key.in_(list(keys)),
    ).all()
    return {r.key: r.value for r in rows if r.value not in (None, "")}


def set_setting(db: Session, restaurant_id: int, key: str, value: Optional[str]):
    row = db.query(AppSettings).filter(
        AppSettings.restaurant_id == restaurant_id,
        AppSettings.key == key,
    ).first()
    if row:
        row.value = value
    else:
        db.add(AppSettings(restaurant_id=restaurant_id, key=key, value=value))


def as_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def as_float(value: Optional[str], default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass
class TaxConfig:
    vat_enabled: bool = True
    vat_rate: float = VAT_RATE
    service_enabled: bool = SERVICE_CHARGE_ENABLED
    service_rate: float = SERVICE_CHARGE_RATE

    def as_dict(self) -> dict:
        return {
            "vat_enabled": self.vat_enabled,
            "vat_rate": self.vat_rate,
            "service_charge_enabled": self.service_enabled,
            "service_charge_rate": self.service_rate,
        }


def tax_config(db: Session, restaurant_id: Optional[int]) -> TaxConfig:
    if not restaurant_id:
        return TaxConfig()
    s = get_settings(db, restaurant_id, ("vat_enabled", "vat_rate",
                                         "service_charge_enabled", "service_charge_rate"))
    return TaxConfig(
        vat_enabled=as_bool(s.get("vat_enabled"), True),
        vat_rate=as_float(s.get("vat_rate"), VAT_RATE),
        service_enabled=as_bool(s.get("service_charge_enabled"), SERVICE_CHARGE_ENABLED),
        service_rate=as_float(s.get("service_charge_rate"), SERVICE_CHARGE_RATE),
    )


def enabled_payment_methods(db: Session, restaurant_id: Optional[int]) -> list[str]:
    raw = DEFAULT_PAYMENT_METHODS
    if restaurant_id:
        raw = get_setting(db, restaurant_id, "payment_methods", DEFAULT_PAYMENT_METHODS)
    keys = [k.strip() for k in raw.split(",") if k.strip() in PAYMENT_METHODS]
    return keys or ["cash"]


def quick_notes(db: Session, restaurant_id: int) -> list[str]:
    raw = get_setting(db, restaurant_id, "quick_notes", DEFAULT_QUICK_NOTES)
    return [n.strip() for n in raw.split(",") if n.strip()]


def printer_path(db: Session, restaurant_id: Optional[int]) -> str:
    """Per-restaurant printer path, falling back to THERMAL_PRINTER_PATH from .env."""
    if restaurant_id:
        path = get_setting(db, restaurant_id, "thermal_printer_path")
        if path:
            return path.strip()
    return THERMAL_PRINTER_PATH.strip()
