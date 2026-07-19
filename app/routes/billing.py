import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db, db_transaction
from app.models.bill import Bill
from app.models.order import Order, OrderItem
from app.models.menu import MenuItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.models.inventory import Ingredient
from app.models.recipe import RecipeIngredient
from app.models.audit import AuditTrail
from app.routes.auth import get_current_user, require_roles, require_admin
from app.config import VAT_RATE, SERVICE_CHARGE_RATE, SERVICE_CHARGE_ENABLED
from app.services import fonepay as fonepay_svc

_log = logging.getLogger(__name__)

# Billing: admin + cashier only; void requires admin
_billing_user = require_roles("admin", "cashier", "superadmin")

router = APIRouter(prefix="/api/billing", tags=["billing"])


# --- Helpers ---

def _nepal_fiscal_year() -> str:
    now = datetime.now(timezone.utc)
    if now.month < 7 or (now.month == 7 and now.day < 16):
        nepali_start = now.year + 56
    else:
        nepali_start = now.year + 57
    return f"{nepali_start}/{str(nepali_start + 1)[-2:]}"


def _next_bill_number(db: Session, fiscal_year: str) -> str:
    count = db.query(Bill).filter(Bill.fiscal_year == fiscal_year).count()
    seq = str(count + 1).zfill(6)
    return f"{fiscal_year}-{seq}"


def _order_subtotal(order_id: int, db: Session) -> tuple[float, list]:
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    lines = []
    subtotal = 0.0
    for oi in items:
        mi = db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first()
        line_total = oi.quantity * oi.unit_price
        subtotal += line_total
        lines.append({
            "name": mi.name if mi else "Unknown",
            "quantity": oi.quantity,
            "unit_price": oi.unit_price,
            "line_total": round(line_total, 2),
            "is_vat_applicable": mi.is_vat_applicable if mi else True,
        })
    return round(subtotal, 2), lines


def _compute_totals(subtotal: float, discount_type: Optional[str],
                    discount_value: float, include_service: bool) -> dict:
    if discount_type == "percentage":
        discount_amount = round(subtotal * discount_value / 100, 2)
    elif discount_type == "flat":
        discount_amount = round(min(discount_value, subtotal), 2)
    else:
        discount_amount = 0.0

    taxable_amount = round(subtotal - discount_amount, 2)
    vat_amount = round(taxable_amount * VAT_RATE / 100, 2)

    if include_service and SERVICE_CHARGE_ENABLED:
        service_charge = round(taxable_amount * SERVICE_CHARGE_RATE / 100, 2)
    else:
        service_charge = 0.0

    grand_total = round(taxable_amount + vat_amount + service_charge, 2)
    return {
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "vat_amount": vat_amount,
        "service_charge": service_charge,
        "grand_total": grand_total,
    }


def _bill_response(bill: Bill, db: Session) -> dict:
    subtotal, lines = _order_subtotal(bill.order_id, db)
    order = db.query(Order).filter(Order.id == bill.order_id).first()
    table_number = None
    if order and order.table_id:
        tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if tbl:
            table_number = tbl.table_number
    cashier_name = None
    if bill.cashier_id:
        u = db.query(User).filter(User.id == bill.cashier_id).first()
        if u:
            cashier_name = u.full_name

    return {
        "id": bill.id,
        "bill_number": bill.bill_number,
        "fiscal_year": bill.fiscal_year,
        "order_id": bill.order_id,
        "order_type": order.order_type if order else None,
        "table_number": table_number,
        "subtotal": bill.subtotal,
        "discount_type": bill.discount_type,
        "discount_value": bill.discount_value,
        "discount_amount": bill.discount_amount,
        "taxable_amount": bill.taxable_amount,
        "vat_amount": bill.vat_amount,
        "service_charge": bill.service_charge,
        "grand_total": bill.grand_total,
        "payment_method": bill.payment_method,
        "payment_status": bill.payment_status,
        "customer_name": bill.customer_name,
        "customer_pan": bill.customer_pan,
        "cashier_name": cashier_name,
        "is_printed": bill.is_printed,
        "print_count": bill.print_count,
        "synced_to_cbms": bill.synced_to_cbms,
        "created_at": bill.created_at.isoformat() if bill.created_at else None,
        "items": lines,
    }


def _deduct_inventory(order_id: int, db: Session, restore: bool = False) -> None:
    """Adjust ingredient stock based on order items and their recipes.
    Silently skips items with no recipe — inventory is optional, not required to bill."""
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    for oi in items:
        recipes = db.query(RecipeIngredient).filter(
            RecipeIngredient.menu_item_id == oi.menu_item_id
        ).all()
        for ri in recipes:
            ing = db.query(Ingredient).filter(Ingredient.id == ri.ingredient_id).first()
            if ing:
                delta = round(ri.quantity_used * oi.quantity, 4)
                if restore:
                    ing.current_stock = round(ing.current_stock + delta, 4)
                else:
                    ing.current_stock = max(0.0, round(ing.current_stock - delta, 4))


def _add_audit(db: Session, restaurant_id, user_id: int,
               action: str, record_id: int, detail: dict = None):
    db.add(AuditTrail(
        restaurant_id=restaurant_id,
        user_id=user_id,
        action=action,
        table_name="bills",
        record_id=record_id,
        new_value=json.dumps(detail) if detail else None,
    ))


# --- Schemas ---

class BillCreate(BaseModel):
    order_id: int
    discount_type: Optional[str] = None
    discount_value: float = 0.0
    include_service_charge: bool = True
    customer_name: Optional[str] = None
    customer_pan: Optional[str] = None

class BillPay(BaseModel):
    payment_method: str
    amount_tendered: Optional[float] = None

class BillUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_pan: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None

class VoidReason(BaseModel):
    reason: str


# --- Endpoints ---

@router.post("/bills", status_code=status.HTTP_201_CREATED)
def create_bill(body: BillCreate, db: Session = Depends(get_db),
                current_user: User = Depends(_billing_user)):
    # --- Validation (before transaction) ---
    q = db.query(Order).filter(Order.id == body.order_id)
    if current_user.restaurant_id:
        q = q.filter(Order.restaurant_id == current_user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("active", "completed"):
        raise HTTPException(status_code=400, detail="Order must be active or completed to bill")

    existing = db.query(Bill).filter(Bill.order_id == body.order_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Bill already exists for this order",
                            headers={"X-Bill-Id": str(existing.id)})

    subtotal, _ = _order_subtotal(body.order_id, db)
    if subtotal == 0:
        raise HTTPException(status_code=400, detail="Order has no items")

    # --- Atomic transaction: create bill ---
    with db_transaction(db):
        fiscal_year = _nepal_fiscal_year()
        bill_number = _next_bill_number(db, fiscal_year)
        totals = _compute_totals(subtotal, body.discount_type,
                                 body.discount_value, body.include_service_charge)

        bill = Bill(
            restaurant_id=current_user.restaurant_id,
            order_id=body.order_id,
            bill_number=bill_number,
            fiscal_year=fiscal_year,
            subtotal=subtotal,
            discount_type=body.discount_type,
            discount_value=body.discount_value,
            discount_amount=totals["discount_amount"],
            taxable_amount=totals["taxable_amount"],
            vat_amount=totals["vat_amount"],
            service_charge=totals["service_charge"],
            grand_total=totals["grand_total"],
            payment_status="unpaid",
            customer_name=body.customer_name or order.customer_name,
            customer_pan=body.customer_pan,
            cashier_id=current_user.id,
        )
        db.add(bill)
        db.flush()  # assign bill.id

        _add_audit(db, current_user.restaurant_id, current_user.id,
                   "CREATE_BILL", bill.id,
                   {"bill_number": bill_number, "grand_total": totals["grand_total"]})
        db.commit()
        db.refresh(bill)

    return _bill_response(bill, db)


@router.get("/bills")
def list_bills(
    payment_status: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(_billing_user),
):
    q = db.query(Bill)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    if payment_status:
        q = q.filter(Bill.payment_status == payment_status)
    if fiscal_year:
        q = q.filter(Bill.fiscal_year == fiscal_year)
    bills = q.order_by(Bill.created_at.desc()).limit(limit).all()
    return [_bill_response(b, db) for b in bills]


@router.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return _bill_response(bill, db)


@router.get("/bills/by-order/{order_id}")
def get_bill_by_order(order_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.order_id == order_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="No bill for this order")
    return _bill_response(bill, db)


@router.post("/bills/{bill_id}/pay")
def pay_bill(bill_id: int, body: BillPay, db: Session = Depends(get_db),
             current_user: User = Depends(_billing_user)):
    valid_methods = {"cash", "card", "qr", "esewa", "khalti"}
    if body.payment_method not in valid_methods:
        raise HTTPException(status_code=400,
                            detail=f"payment_method must be one of {sorted(valid_methods)}")

    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Bill is already paid")
    if bill.payment_status == "void":
        raise HTTPException(status_code=400, detail="Cannot pay a voided bill")

    # --- Atomic transaction: pay bill + update order/table + deduct inventory ---
    with db_transaction(db):
        bill.payment_method = body.payment_method
        bill.payment_status = "paid"

        order = db.query(Order).filter(Order.id == bill.order_id).first()
        if order:
            order.status = "completed"
            if order.table_id:
                tbl = db.query(RestaurantTable).filter(
                    RestaurantTable.id == order.table_id
                ).first()
                if tbl:
                    tbl.status = "free"

        _deduct_inventory(bill.order_id, db)
        _add_audit(db, current_user.restaurant_id, current_user.id,
                   "PAY_BILL", bill.id,
                   {"payment_method": body.payment_method, "grand_total": bill.grand_total})
        db.commit()
        db.refresh(bill)

    change = None
    if body.payment_method == "cash" and body.amount_tendered is not None:
        change = round(body.amount_tendered - bill.grand_total, 2)

    resp = _bill_response(bill, db)
    if change is not None:
        resp["change"] = change
    return resp


@router.post("/bills/{bill_id}/void")
def void_bill(bill_id: int, body: VoidReason, db: Session = Depends(get_db),
              current_user: User = Depends(require_admin)):
    """Admin-only. Void a bill: restores inventory, frees table, logs audit trail."""
    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.payment_status == "void":
        raise HTTPException(status_code=409, detail="Bill is already voided")

    was_paid = bill.payment_status == "paid"

    with db_transaction(db):
        bill.payment_status = "void"

        order = db.query(Order).filter(Order.id == bill.order_id).first()
        if order:
            order.status = "cancelled"
            if order.table_id:
                tbl = db.query(RestaurantTable).filter(
                    RestaurantTable.id == order.table_id
                ).first()
                if tbl:
                    tbl.status = "free"

        # Restore inventory only if the bill was paid (inventory was deducted at pay time)
        if was_paid:
            _deduct_inventory(bill.order_id, db, restore=True)

        db.add(AuditTrail(
            restaurant_id=current_user.restaurant_id,
            user_id=current_user.id,
            action="VOID_BILL",
            table_name="bills",
            record_id=bill.id,
            reason=body.reason,
            new_value=json.dumps({"was_paid": was_paid,
                                  "grand_total": bill.grand_total}),
        ))
        db.commit()
        db.refresh(bill)

    return _bill_response(bill, db)


@router.patch("/bills/{bill_id}/print")
def record_print(bill_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill.is_printed = True
    bill.print_count += 1
    db.commit()
    return {"bill_id": bill.id, "print_count": bill.print_count}


@router.patch("/bills/{bill_id}/update")
def update_bill(bill_id: int, body: BillUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Cannot modify a paid bill")
    if bill.payment_status == "void":
        raise HTTPException(status_code=400, detail="Cannot modify a voided bill")

    if body.customer_name is not None:
        bill.customer_name = body.customer_name
    if body.customer_pan is not None:
        bill.customer_pan = body.customer_pan
    if body.discount_type is not None or body.discount_value is not None:
        dt = body.discount_type if body.discount_type is not None else bill.discount_type
        dv = body.discount_value if body.discount_value is not None else bill.discount_value
        totals = _compute_totals(bill.subtotal, dt, dv, bill.service_charge > 0)
        bill.discount_type = dt
        bill.discount_value = dv
        bill.discount_amount = totals["discount_amount"]
        bill.taxable_amount = totals["taxable_amount"]
        bill.vat_amount = totals["vat_amount"]
        bill.service_charge = totals["service_charge"]
        bill.grand_total = totals["grand_total"]

    db.commit()
    db.refresh(bill)
    return _bill_response(bill, db)


@router.post("/bills/{bill_id}/fonepay-qr")
async def initiate_fonepay_qr(bill_id: int, db: Session = Depends(get_db),
                               _=Depends(_billing_user)):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Bill is already paid")

    try:
        result = await fonepay_svc.initiate_qr(
            bill_id=bill.id,
            amount=bill.grand_total,
            remarks=f"Bill {bill.bill_number}",
        )
    except Exception as exc:
        _log.exception("FonePay QR initiation failed for bill %s", bill_id)
        raise HTTPException(status_code=502, detail=f"FonePay API error: {exc}")

    bill.fonepay_prn = result["prn"]
    db.commit()

    return {
        "prn":      result["prn"],
        "qr_data":  result["qr_data"],
        "qr_image": result["qr_image"],
        "amount":   bill.grand_total,
    }


@router.post("/fonepay/callback")
async def fonepay_callback(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    prn  = form.get("PRN", "")
    bid  = form.get("BID", "")
    amt  = form.get("AMT", "")
    uid  = form.get("UID", "")
    bc   = form.get("BC", "")
    ini  = form.get("INI", "")
    hash_received = form.get("hashCode", "")

    if not fonepay_svc.verify_callback(prn, bid, amt, uid, bc, ini, hash_received):
        raise HTTPException(status_code=400, detail="Invalid FonePay signature")

    bill = db.query(Bill).filter(Bill.fonepay_prn == prn).first()
    if not bill:
        raise HTTPException(status_code=404, detail="No bill for this PRN")

    if bill.payment_status != "paid":
        with db_transaction(db):
            bill.payment_method = "qr"
            bill.payment_status = "paid"

            order = db.query(Order).filter(Order.id == bill.order_id).first()
            if order:
                order.status = "completed"
                if order.table_id:
                    tbl = db.query(RestaurantTable).filter(
                        RestaurantTable.id == order.table_id
                    ).first()
                    if tbl:
                        tbl.status = "free"

            _deduct_inventory(bill.order_id, db)
            db.commit()

    return {"status": "ok"}


@router.get("/bills/{bill_id}/payment-status")
def payment_status(bill_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.id == bill_id)
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return {"bill_id": bill.id, "payment_status": bill.payment_status,
            "payment_method": bill.payment_method}


@router.get("/summary/today")
def today_summary(db: Session = Depends(get_db),
                  current_user: User = Depends(_billing_user)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    q = db.query(Bill).filter(
        Bill.payment_status == "paid",
        Bill.created_at >= today_start,
    )
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bills = q.all()

    total_sales = round(sum(b.grand_total for b in bills), 2)
    total_vat = round(sum(b.vat_amount for b in bills), 2)
    total_service = round(sum(b.service_charge for b in bills), 2)
    by_method: dict[str, float] = {}
    for b in bills:
        m = b.payment_method or "unknown"
        by_method[m] = round(by_method.get(m, 0) + b.grand_total, 2)

    return {
        "date": today_start.date().isoformat(),
        "bill_count": len(bills),
        "total_sales": total_sales,
        "total_vat_collected": total_vat,
        "total_service_charge": total_service,
        "by_payment_method": by_method,
    }
