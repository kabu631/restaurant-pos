"""
Bill arithmetic — the only place totals are computed (the UI asks the
/api/billing/preview endpoint instead of re-implementing it).

Nepal convention: the service charge is levied on the amount after discount,
and VAT on (amount + service charge):

    Subtotal 1,000.00 → Service charge 10% 100.00 → Taxable 1,100.00
    → VAT 13% 143.00 → Grand total 1,243.00

Items marked "VAT not applicable" are excluded from the taxable amount pro rata.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.menu import MenuItem
from app.models.order import OrderItem
from app.services.restaurant_settings import TaxConfig

DISCOUNT_TYPES = (None, "percentage", "flat")


def order_lines(db: Session, order_id: int) -> list[dict]:
    """Billable lines for an order: void items dropped, repeat rounds of the
    same dish at the same price merged into one line."""
    rows = (
        db.query(OrderItem, MenuItem)
        .outerjoin(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .filter(OrderItem.order_id == order_id, OrderItem.kot_status != "void")
        .order_by(OrderItem.id)
        .all()
    )
    merged: dict[tuple, dict] = {}
    for oi, mi in rows:
        key = (oi.menu_item_id, oi.unit_price)
        line = merged.get(key)
        if line is None:
            line = merged[key] = {
                "menu_item_id": oi.menu_item_id,
                "name": mi.name if mi else "Unknown",
                "quantity": 0,
                "unit_price": oi.unit_price,
                "line_total": 0.0,
                "is_vat_applicable": mi.is_vat_applicable if mi else True,
            }
        line["quantity"] += oi.quantity
        line["line_total"] = round(line["quantity"] * oi.unit_price, 2)
    return list(merged.values())


def validate_discount(discount_type: Optional[str], discount_value: float) -> Optional[str]:
    """Normalise and validate a discount; returns the cleaned type."""
    discount_type = discount_type or None
    if discount_type not in DISCOUNT_TYPES:
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'flat'")
    if discount_value is None or discount_value < 0:
        raise HTTPException(status_code=400, detail="Discount cannot be negative")
    if discount_type == "percentage" and discount_value > 100:
        raise HTTPException(status_code=400, detail="Percentage discount cannot exceed 100%")
    return discount_type


def compute_totals(lines: list[dict], discount_type: Optional[str], discount_value: float,
                   include_service: bool, cfg: TaxConfig) -> dict:
    subtotal = round(sum(l["line_total"] for l in lines), 2)
    vatable_subtotal = round(sum(l["line_total"] for l in lines if l["is_vat_applicable"]), 2)

    if discount_type == "percentage":
        discount_amount = round(subtotal * discount_value / 100, 2)
    elif discount_type == "flat":
        discount_amount = round(min(discount_value, subtotal), 2)
    else:
        discount_amount = 0.0
    net = round(subtotal - discount_amount, 2)

    apply_service = include_service and cfg.service_enabled
    service_charge = round(net * cfg.service_rate / 100, 2) if apply_service else 0.0

    if cfg.vat_enabled and subtotal > 0:
        taxable_amount = round((net + service_charge) * vatable_subtotal / subtotal, 2)
        vat_amount = round(taxable_amount * cfg.vat_rate / 100, 2)
    else:
        taxable_amount = 0.0
        vat_amount = 0.0

    grand_total = round(net + service_charge + vat_amount, 2)
    return {
        "subtotal": subtotal,
        "discount_type": discount_type,
        "discount_value": discount_value if discount_type else 0.0,
        "discount_amount": discount_amount,
        "net_amount": net,
        "service_charge": service_charge,
        "service_charge_rate": cfg.service_rate if apply_service else 0.0,
        "taxable_amount": taxable_amount,
        "non_taxable_amount": round(net + service_charge - taxable_amount, 2),
        "vat_amount": vat_amount,
        "vat_rate": cfg.vat_rate if cfg.vat_enabled else 0.0,
        "grand_total": grand_total,
    }


def apply_totals(bill: Bill, totals: dict) -> None:
    bill.subtotal        = totals["subtotal"]
    bill.discount_type   = totals["discount_type"]
    bill.discount_value  = totals["discount_value"]
    bill.discount_amount = totals["discount_amount"]
    bill.taxable_amount  = totals["taxable_amount"]
    bill.vat_amount      = totals["vat_amount"]
    bill.service_charge  = totals["service_charge"]
    bill.grand_total     = totals["grand_total"]
