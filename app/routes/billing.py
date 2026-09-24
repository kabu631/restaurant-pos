import logging
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config import FONEPAY_MERCHANT_CODE
from app.database import get_db, db_transaction
from app.models.bill import Bill, BillPayment
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.models.inventory import Ingredient
from app.models.recipe import RecipeIngredient
from app.routes.auth import get_current_user, require_roles, require_admin
from app.services import audit
from app.services import fonepay as fonepay_svc
from app.services import order_ops as ops
from app.services import printer as printer_svc
from app.services.billing_calc import apply_totals, compute_totals, order_lines, validate_discount
from app.services.customers import upsert_customer
from app.services.restaurant_settings import (PAYMENT_METHODS, QR_METHODS, enabled_payment_methods,
                                              get_setting, printer_path, tax_config)
from app.utils import nepal

_log = logging.getLogger(__name__)

# Billing: admin + cashier only; void requires admin
_billing_user = require_roles("admin", "cashier", "superadmin")

router = APIRouter(prefix="/api/billing", tags=["billing"])


# --- Helpers ---

def _nepal_fiscal_year() -> str:
    return nepal.fiscal_year()


def _next_bill_number(db: Session, restaurant_id: int, fiscal_year: str) -> str:
    """Next gap-free invoice number for this restaurant and fiscal year (IRD).
    Takes the restaurant row lock so two tills can never issue the same number."""
    ops.lock_restaurant(db, restaurant_id)
    last = db.query(func.max(Bill.bill_number)).filter(
        Bill.restaurant_id == restaurant_id,
        Bill.fiscal_year == fiscal_year,
    ).scalar()
    try:
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    except (ValueError, IndexError):
        seq = db.query(Bill).filter(Bill.restaurant_id == restaurant_id,
                                    Bill.fiscal_year == fiscal_year).count() + 1
    return f"{fiscal_year}-{str(seq).zfill(6)}"


def _rate(part: float, base: float) -> float:
    return round(part / base * 100, 1) if base else 0.0


def _payments_out(db: Session, bill: Bill) -> list:
    rows = db.query(BillPayment).filter(BillPayment.bill_id == bill.id).order_by(BillPayment.id).all()
    return [{
        "method": p.method,
        "label": PAYMENT_METHODS.get(p.method, p.method.title()),
        "amount": p.amount,
        "tendered": p.tendered,
        "reference": p.reference,
        "created_at": nepal.iso(p.created_at),
    } for p in rows]


def _bill_response(bill: Bill, db: Session) -> dict:
    lines = order_lines(db, bill.order_id)
    order = db.get(Order, bill.order_id)
    table_number = None
    if order and order.table_id:
        tbl = db.get(RestaurantTable, order.table_id)
        table_number = tbl.table_number if tbl else None
    cashier = db.get(User, bill.cashier_id) if bill.cashier_id else None
    payments = _payments_out(db, bill)
    change = round(sum((p["tendered"] or p["amount"]) - p["amount"] for p in payments), 2)
    net = (bill.subtotal or 0) - (bill.discount_amount or 0)
    created = nepal.to_npt(bill.created_at)

    return {
        "id": bill.id,
        "bill_number": bill.bill_number,
        "fiscal_year": bill.fiscal_year,
        "order_id": bill.order_id,
        "order_type": order.order_type if order else None,
        "table_number": table_number,
        "guests": order.guests if order else None,
        "subtotal": bill.subtotal,
        "discount_type": bill.discount_type,
        "discount_value": bill.discount_value,
        "discount_amount": bill.discount_amount,
        "taxable_amount": bill.taxable_amount,
        "vat_amount": bill.vat_amount,
        "vat_rate": _rate(bill.vat_amount or 0, bill.taxable_amount or 0),
        "service_charge": bill.service_charge,
        "service_charge_rate": _rate(bill.service_charge or 0, net),
        "grand_total": bill.grand_total,
        "payment_method": bill.payment_method,
        "payment_status": bill.payment_status,
        "payments": payments,
        "change": change if change > 0 else None,
        "customer_name": bill.customer_name,
        "customer_pan": bill.customer_pan,
        "cashier_name": cashier.full_name if cashier else None,
        "is_printed": bill.is_printed,
        "print_count": bill.print_count,
        "synced_to_cbms": bill.synced_to_cbms,
        "created_at": nepal.iso(bill.created_at),
        "date_display": created.strftime("%Y-%m-%d %H:%M") if created else "",
        "items": lines,
    }


def _deduct_inventory(order_id: int, db: Session, restore: bool = False) -> None:
    """Adjust ingredient stock based on order items and their recipes.
    Silently skips items with no recipe — inventory is optional, not required to bill."""
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id,
                                       OrderItem.kot_status != "void").all()
    for oi in items:
        recipes = db.query(RecipeIngredient).filter(
            RecipeIngredient.menu_item_id == oi.menu_item_id
        ).all()
        for ri in recipes:
            ing = db.get(Ingredient, ri.ingredient_id)
            if ing:
                delta = round(ri.quantity_used * oi.quantity, 4)
                if restore:
                    ing.current_stock = round(ing.current_stock + delta, 4)
                else:
                    ing.current_stock = max(0.0, round(ing.current_stock - delta, 4))


def _get_bill(db: Session, bill_id: int, user: User) -> Bill:
    q = db.query(Bill).filter(Bill.id == bill_id)
    if user.restaurant_id:
        q = q.filter(Bill.restaurant_id == user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def _open_bill_for(db: Session, order_id: int) -> Optional[Bill]:
    return (db.query(Bill)
              .filter(Bill.order_id == order_id, Bill.payment_status != "void")
              .order_by(Bill.id.desc()).first())


def _new_bill(db: Session, order: Order, user: User) -> Bill:
    fy = nepal.fiscal_year()
    bill = Bill(
        restaurant_id=order.restaurant_id,
        order_id=order.id,
        bill_number=_next_bill_number(db, order.restaurant_id, fy),
        fiscal_year=fy,
        subtotal=0.0,
        taxable_amount=0.0,
        grand_total=0.0,
        payment_status="unpaid",
        cashier_id=user.id,
    )
    db.add(bill)
    return bill


def _settle(db: Session, bill: Bill, methods: list) -> None:
    """Mark the bill paid and close out the order, table, stock and customer record."""
    bill.payment_status = "paid"
    bill.payment_method = methods[0] if len(set(methods)) == 1 else "split"
    order = db.get(Order, bill.order_id)
    if order:
        order.status = "completed"
        ops.release_table(db, order)
        upsert_customer(db, bill.restaurant_id, order.customer_name or bill.customer_name,
                        order.customer_phone, spent=bill.grand_total, visit=True)
    _deduct_inventory(bill.order_id, db)


# --- Schemas ---

class BillCreate(BaseModel):
    order_id: int
    discount_type: Optional[str] = None
    discount_value: float = 0.0
    include_service_charge: bool = True
    customer_name: Optional[str] = None
    customer_pan: Optional[str] = None

class BillPreview(BaseModel):
    order_id: int
    discount_type: Optional[str] = None
    discount_value: float = 0.0
    include_service_charge: bool = True

class PaymentIn(BaseModel):
    method: str
    amount: Optional[float] = None      # omit for a single payment of the full amount
    tendered: Optional[float] = None    # cash handed over
    reference: Optional[str] = None     # wallet / card transaction id

class CheckoutRequest(BaseModel):
    order_id: int
    discount_type: Optional[str] = None
    discount_value: float = 0.0
    include_service_charge: bool = True
    customer_name: Optional[str] = None
    customer_pan: Optional[str] = None
    payments: List[PaymentIn]

class BillPay(BaseModel):
    payment_method: str
    amount_tendered: Optional[float] = None
    reference: Optional[str] = None

class BillUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_pan: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    include_service_charge: Optional[bool] = None

class VoidReason(BaseModel):
    reason: str


def _validate_payments(db: Session, restaurant_id: int, payments: List[PaymentIn],
                       grand_total: float) -> List[PaymentIn]:
    if not payments:
        raise HTTPException(status_code=400, detail="Choose a payment method")
    enabled = enabled_payment_methods(db, restaurant_id)
    if len(payments) == 1 and payments[0].amount is None:
        payments[0].amount = grand_total
    total = 0.0
    for p in payments:
        if p.method not in PAYMENT_METHODS:
            raise HTTPException(status_code=400,
                                detail=f"payment method must be one of {sorted(PAYMENT_METHODS)}")
        if p.method not in enabled:
            raise HTTPException(status_code=400,
                                detail=f"{PAYMENT_METHODS[p.method]} is turned off in Settings")
        if p.amount is None or p.amount <= 0:
            raise HTTPException(status_code=400, detail="Each payment needs an amount above zero")
        p.amount = round(p.amount, 2)
        if p.method != "cash":
            p.tendered = None
        elif p.tendered is not None and p.tendered + 0.005 < p.amount:
            raise HTTPException(status_code=400,
                                detail=f"Cash received ({p.tendered:.2f}) is less than {p.amount:.2f}")
        p.reference = (p.reference or "").strip()[:100] or None
        total += p.amount
    if abs(round(total, 2) - grand_total) > 0.01:
        raise HTTPException(status_code=400,
                            detail=f"Payments add up to {total:.2f} but the bill is {grand_total:.2f}")
    return payments


# --- Endpoints ---

@router.get("/payment-methods")
def payment_methods(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Enabled tenders with the restaurant's uploaded merchant QR images, plus tax config."""
    rid = current_user.restaurant_id
    methods = []
    for key in enabled_payment_methods(db, rid):
        qr_image = get_setting(db, rid, f"qr_image_{key}") if (rid and key in QR_METHODS) else None
        methods.append({"key": key, "label": PAYMENT_METHODS[key], "qr_image": qr_image})
    return {
        "methods": methods,
        "fonepay_dynamic": FONEPAY_MERCHANT_CODE not in ("", "DEMO_PID"),
        "tax": tax_config(db, rid).as_dict(),
    }


@router.post("/preview")
def preview_bill(body: BillPreview, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Totals for an order with the given discount — nothing is saved."""
    order = ops.get_order(db, body.order_id, current_user)
    discount_type = validate_discount(body.discount_type, body.discount_value)
    lines = order_lines(db, order.id)
    totals = compute_totals(lines, discount_type, body.discount_value,
                            body.include_service_charge, tax_config(db, order.restaurant_id))
    table = db.get(RestaurantTable, order.table_id) if order.table_id else None
    pending = db.query(OrderItem).filter(OrderItem.order_id == order.id,
                                         OrderItem.kot_status == "pending").count()
    awaiting = db.query(OrderItem).filter(OrderItem.order_id == order.id,
                                          OrderItem.kot_status == "sent").count()
    bill = _open_bill_for(db, order.id)
    return {
        **totals,
        "order_id": order.id,
        "order_type": order.order_type,
        "table_number": table.table_number if table else None,
        "customer_name": order.customer_name,
        "pending_items": pending,
        "awaiting_accept": awaiting,          # sent, but the kitchen hasn't accepted yet
        "items": lines,
        # The bill already created (and maybe printed) for this order, awaiting payment
        "bill": ({"id": bill.id, "bill_number": bill.bill_number, "print_count": bill.print_count or 0,
                  "customer_name": bill.customer_name, "customer_pan": bill.customer_pan,
                  "discount_type": bill.discount_type, "discount_value": bill.discount_value or 0,
                  "include_service_charge": (bill.service_charge or 0) > 0}
                 if bill and bill.payment_status == "unpaid" else None),
    }


@router.post("/checkout")
def checkout(body: CheckoutRequest, db: Session = Depends(get_db),
             current_user: User = Depends(_billing_user)):
    """Settle an order in one step: issue the bill (or reuse its open one), record the
    payment(s), close the order and free the table.  Unsent items go to the kitchen."""
    rid = ops.restaurant_id_of(current_user)
    order = ops.get_order(db, body.order_id, current_user)
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="This order was cancelled")
    bill = _open_bill_for(db, order.id)
    if bill and bill.payment_status == "paid":
        raise HTTPException(status_code=409, detail=f"Already paid — bill {bill.bill_number}",
                            headers={"X-Bill-Id": str(bill.id)})

    discount_type = validate_discount(body.discount_type, body.discount_value)
    lines = order_lines(db, order.id)
    if not lines:
        raise HTTPException(status_code=400, detail="Order has no items")
    totals = compute_totals(lines, discount_type, body.discount_value,
                            body.include_service_charge, tax_config(db, rid))
    payments = _validate_payments(db, rid, body.payments, totals["grand_total"])

    with db_transaction(db):
        ops.lock_restaurant(db, rid)
        kot = ops.send_kot(db, order) if order.status == "active" else None
        if bill is None:
            bill = _new_bill(db, order, current_user)
        apply_totals(bill, totals)
        bill.cashier_id = current_user.id
        bill.customer_name = (body.customer_name or "").strip() or bill.customer_name or order.customer_name
        bill.customer_pan = (body.customer_pan or "").strip() or bill.customer_pan
        db.flush()
        for p in payments:
            db.add(BillPayment(restaurant_id=rid, bill_id=bill.id, method=p.method,
                               amount=p.amount, tendered=p.tendered, reference=p.reference,
                               received_by=current_user.id))
        _settle(db, bill, [p.method for p in payments])
        audit.record(db, current_user, "PAY_BILL", "bills", bill.id, {
            "bill_number": bill.bill_number,
            "grand_total": bill.grand_total,
            "payments": [{"method": p.method, "amount": p.amount} for p in payments],
        })
        db.commit()
        db.refresh(bill)

    resp = _bill_response(bill, db)
    if kot:
        resp["kot"] = ops.dispatch_kot_print(db, order, kot)
    return resp


@router.post("/bills", status_code=status.HTTP_201_CREATED)
def create_bill(body: BillCreate, db: Session = Depends(get_db),
                current_user: User = Depends(_billing_user)):
    """Create the bill for an order so it can be printed for the guest; payment is
    taken later (checkout reuses this bill and its number).  Anything not yet sent
    goes to the kitchen now — billed food must always be made."""
    rid = ops.restaurant_id_of(current_user)
    order = ops.get_order(db, body.order_id, current_user)
    if order.status not in ("active", "completed"):
        raise HTTPException(status_code=400, detail="Order must be active or completed to bill")

    existing = _open_bill_for(db, order.id)
    if existing:
        raise HTTPException(status_code=409, detail="Bill already exists for this order",
                            headers={"X-Bill-Id": str(existing.id)})

    discount_type = validate_discount(body.discount_type, body.discount_value)
    lines = order_lines(db, order.id)
    if not lines:
        raise HTTPException(status_code=400, detail="Order has no items")

    with db_transaction(db):
        ops.lock_restaurant(db, rid)
        kot = ops.send_kot(db, order) if order.status == "active" else None
        bill = _new_bill(db, order, current_user)
        apply_totals(bill, compute_totals(lines, discount_type, body.discount_value,
                                          body.include_service_charge, tax_config(db, rid)))
        bill.customer_name = (body.customer_name or "").strip() or order.customer_name
        bill.customer_pan = (body.customer_pan or "").strip() or None
        db.flush()  # assign bill.id
        audit.record(db, current_user, "CREATE_BILL", "bills", bill.id,
                     {"bill_number": bill.bill_number, "grand_total": bill.grand_total})
        db.commit()
        db.refresh(bill)

    resp = _bill_response(bill, db)
    if kot:
        resp["kot"] = ops.dispatch_kot_print(db, order, kot)
    return resp


@router.get("/bills")
def list_bills(
    payment_status: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    date: Optional[str] = None,        # YYYY-MM-DD (Nepal time)
    search: Optional[str] = None,      # bill number / customer name
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
    if date:
        try:
            start, end = nepal.day_bounds(date_cls.fromisoformat(date))
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        q = q.filter(Bill.created_at >= start, Bill.created_at < end)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((Bill.bill_number.ilike(like)) | (Bill.customer_name.ilike(like)))
    bills = q.order_by(Bill.created_at.desc(), Bill.id.desc()).limit(max(1, min(limit, 500))).all()
    return [_bill_response(b, db) for b in bills]


@router.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(_billing_user)):
    return _bill_response(_get_bill(db, bill_id, current_user), db)


@router.get("/bills/by-order/{order_id}")
def get_bill_by_order(order_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(_billing_user)):
    q = db.query(Bill).filter(Bill.order_id == order_id, Bill.payment_status != "void")
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bill = q.order_by(Bill.id.desc()).first()
    if not bill:
        raise HTTPException(status_code=404, detail="No bill for this order")
    return _bill_response(bill, db)


@router.post("/bills/{bill_id}/pay")
def pay_bill(bill_id: int, body: BillPay, db: Session = Depends(get_db),
             current_user: User = Depends(_billing_user)):
    bill = _get_bill(db, bill_id, current_user)
    if bill.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Bill is already paid")
    if bill.payment_status == "void":
        raise HTTPException(status_code=400, detail="Cannot pay a voided bill")
    (payment,) = _validate_payments(db, bill.restaurant_id, [PaymentIn(
        method=body.payment_method, amount=bill.grand_total,
        tendered=body.amount_tendered, reference=body.reference,
    )], bill.grand_total)

    # --- Atomic transaction: pay bill + update order/table + deduct inventory ---
    with db_transaction(db):
        db.add(BillPayment(restaurant_id=bill.restaurant_id, bill_id=bill.id,
                           method=payment.method, amount=payment.amount,
                           tendered=payment.tendered, reference=payment.reference,
                           received_by=current_user.id))
        _settle(db, bill, [payment.method])
        audit.record(db, current_user, "PAY_BILL", "bills", bill.id,
                     {"payment_method": payment.method, "grand_total": bill.grand_total})
        db.commit()
        db.refresh(bill)

    return _bill_response(bill, db)


@router.post("/bills/{bill_id}/void")
def void_bill(bill_id: int, body: VoidReason, db: Session = Depends(get_db),
              current_user: User = Depends(require_admin)):
    """Admin-only.  Voiding a paid bill (refund) restores stock and cancels the order;
    voiding an unpaid bill keeps the order open so it can be billed again."""
    bill = _get_bill(db, bill_id, current_user)
    if bill.payment_status == "void":
        raise HTTPException(status_code=409, detail="Bill is already voided")
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="A reason is required to void a bill")

    was_paid = bill.payment_status == "paid"

    with db_transaction(db):
        bill.payment_status = "void"
        order = db.get(Order, bill.order_id)
        if order and was_paid:
            order.status = "cancelled"
            ops.release_table(db, order)
            # Inventory was deducted at pay time — put it back
            _deduct_inventory(bill.order_id, db, restore=True)
        audit.record(db, current_user, "VOID_BILL", "bills", bill.id,
                     {"was_paid": was_paid, "grand_total": bill.grand_total,
                      "bill_number": bill.bill_number},
                     reason=body.reason)
        db.commit()
        db.refresh(bill)

    return _bill_response(bill, db)


@router.patch("/bills/{bill_id}/print")
def record_print(bill_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(_billing_user)):
    bill = _get_bill(db, bill_id, current_user)
    bill.is_printed = True
    bill.print_count = (bill.print_count or 0) + 1
    audit.record(db, current_user, "PRINT_BILL" if bill.print_count == 1 else "REPRINT_BILL",
                 "bills", bill.id, {"print_count": bill.print_count})
    db.commit()
    return {"bill_id": bill.id, "print_count": bill.print_count}


@router.post("/bills/{bill_id}/print-thermal")
def print_thermal(bill_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(_billing_user)):
    """Send the receipt to the configured thermal printer (counts as a print)."""
    bill = _get_bill(db, bill_id, current_user)
    path = printer_path(db, bill.restaurant_id)
    if not path:
        raise HTTPException(status_code=400, detail="No thermal printer configured")
    record_print(bill_id, db, current_user)
    rest = db.get(Restaurant, bill.restaurant_id)
    result = printer_svc.print_receipt(_bill_response(bill, db), {
        "name": rest.name if rest else "",
        "address": rest.address if rest else "",
        "phone": rest.phone if rest else "",
        "vat_number": rest.vat_number if rest else "",
        "receipt_footer": get_setting(db, bill.restaurant_id, "receipt_footer"),
    }, path)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Printer error: {result.get('detail')}")
    return result


@router.patch("/bills/{bill_id}/update")
def update_bill(bill_id: int, body: BillUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(_billing_user)):
    bill = _get_bill(db, bill_id, current_user)
    if bill.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Cannot modify a paid bill")
    if bill.payment_status == "void":
        raise HTTPException(status_code=400, detail="Cannot modify a voided bill")

    if body.customer_name is not None:
        bill.customer_name = body.customer_name.strip() or None
    if body.customer_pan is not None:
        bill.customer_pan = body.customer_pan.strip() or None
    if (body.discount_type is not None or body.discount_value is not None
            or body.include_service_charge is not None):
        dt = body.discount_type if body.discount_type is not None else bill.discount_type
        dv = body.discount_value if body.discount_value is not None else (bill.discount_value or 0.0)
        dt = validate_discount(dt, dv)
        service = (body.include_service_charge if body.include_service_charge is not None
                   else (bill.service_charge or 0) > 0)
        apply_totals(bill, compute_totals(order_lines(db, bill.order_id), dt, dv, service,
                                          tax_config(db, bill.restaurant_id)))

    db.commit()
    db.refresh(bill)
    return _bill_response(bill, db)


@router.post("/bills/{bill_id}/fonepay-qr")
async def initiate_fonepay_qr(bill_id: int, db: Session = Depends(get_db),
                              current_user: User = Depends(_billing_user)):
    bill = _get_bill(db, bill_id, current_user)
    if bill.payment_status != "unpaid":
        raise HTTPException(status_code=400, detail=f"Bill is {bill.payment_status}")

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

    if bill.payment_status == "unpaid":
        try:
            if abs(float(amt) - bill.grand_total) > 0.01:
                _log.warning("FonePay amount %s differs from bill %s total %.2f",
                             amt, bill.bill_number, bill.grand_total)
        except ValueError:
            pass
        with db_transaction(db):
            db.add(BillPayment(restaurant_id=bill.restaurant_id, bill_id=bill.id, method="qr",
                               amount=bill.grand_total, reference=(uid or prn)[:100]))
            _settle(db, bill, ["qr"])
            audit.record(db, None, "PAY_BILL", "bills", bill.id,
                         {"payment_method": "qr", "fonepay_prn": prn, "grand_total": bill.grand_total})
            db.commit()

    return {"status": "ok"}


@router.get("/bills/{bill_id}/payment-status")
def payment_status(bill_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(_billing_user)):
    bill = _get_bill(db, bill_id, current_user)
    return {"bill_id": bill.id, "payment_status": bill.payment_status,
            "payment_method": bill.payment_method}


def payment_breakdown(db: Session, bills: list) -> dict:
    """Takings per tender.  Split bills count each part under its own method;
    bills from before split payments existed fall back to bill.payment_method."""
    by_method: dict[str, float] = {}
    if not bills:
        return by_method
    ids = [b.id for b in bills]
    rows = db.query(BillPayment).filter(BillPayment.bill_id.in_(ids)).all()
    with_rows = {r.bill_id for r in rows}
    for r in rows:
        by_method[r.method] = round(by_method.get(r.method, 0) + r.amount, 2)
    for b in bills:
        if b.id not in with_rows:
            m = b.payment_method or "unknown"
            by_method[m] = round(by_method.get(m, 0) + (b.grand_total or 0), 2)
    return by_method


@router.get("/summary/today")
def today_summary(db: Session = Depends(get_db),
                  current_user: User = Depends(_billing_user)):
    today = nepal.today()
    start, end = nepal.day_bounds(today)
    q = db.query(Bill).filter(
        Bill.payment_status == "paid",
        Bill.created_at >= start,
        Bill.created_at < end,
    )
    if current_user.restaurant_id:
        q = q.filter(Bill.restaurant_id == current_user.restaurant_id)
    bills = q.all()

    return {
        "date": today.isoformat(),
        "bill_count": len(bills),
        "total_sales": round(sum(b.grand_total for b in bills), 2),
        "total_vat_collected": round(sum(b.vat_amount or 0 for b in bills), 2),
        "total_service_charge": round(sum(b.service_charge or 0 for b in bills), 2),
        "total_discount": round(sum(b.discount_amount or 0 for b in bills), 2),
        "by_payment_method": payment_breakdown(db, bills),
    }
