"""
Cash drawer shifts: the cashier opens the drawer with a float, records any cash put
in or taken out (petty cash, bank drop), and closes it by counting the cash.  The app
works out what should be there and shows any shortage or overage.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import db_transaction, get_db
from app.models.bill import Bill, BillPayment
from app.models.cash_shift import CashMovement, CashShift
from app.models.user import User
from app.services import audit
from app.services import order_ops as ops
from app.services.permissions import require_perm
from app.services.restaurant_settings import PAYMENT_METHODS
from app.utils import nepal

router = APIRouter(prefix="/api/shifts", tags=["cash shifts"])

_drawer_user = require_perm("cash.shift")
_viewer = require_perm("cash.shift", "reports.view")


class OpenShift(BaseModel):
    opening_float: float = 0.0
    notes: Optional[str] = None

class Movement(BaseModel):
    kind: str            # in / out
    amount: float
    reason: str

class CloseShift(BaseModel):
    counted_cash: float
    notes: Optional[str] = None


def _current(db: Session, rid: int) -> Optional[CashShift]:
    return (db.query(CashShift).filter(CashShift.restaurant_id == rid, CashShift.status == "open")
              .order_by(CashShift.id.desc()).first())


def _name(db: Session, user_id: Optional[int]) -> Optional[str]:
    u = db.get(User, user_id) if user_id else None
    return u.full_name if u else None


def shift_summary(db: Session, shift: CashShift) -> dict:
    """Sales and cash for the shift's time window (live while it is open)."""
    end: datetime = shift.closed_at or nepal.now()
    payments = (db.query(BillPayment, Bill)
                  .join(Bill, Bill.id == BillPayment.bill_id)
                  .filter(BillPayment.restaurant_id == shift.restaurant_id,
                          BillPayment.created_at >= shift.opened_at,
                          BillPayment.created_at <= end)
                  .all())
    by_method: dict[str, float] = {}
    bills, voided = set(), set()
    refunded_cash = 0.0
    for p, b in payments:
        if b.payment_status == "void":
            voided.add(b.id)
            if p.method == "cash":
                refunded_cash += p.amount      # a voided paid bill gives the cash back
            continue
        bills.add(b.id)
        by_method[p.method] = round(by_method.get(p.method, 0.0) + p.amount, 2)
    discounts = sum((b.discount_amount or 0) for b in
                    db.query(Bill).filter(Bill.id.in_(bills)).all()) if bills else 0.0
    moves = (db.query(CashMovement).filter(CashMovement.shift_id == shift.id)
               .order_by(CashMovement.id).all())
    pay_in = round(sum(m.amount for m in moves if m.kind == "in"), 2)
    pay_out = round(sum(m.amount for m in moves if m.kind == "out"), 2)
    cash_sales = by_method.get("cash", 0.0)
    expected = round((shift.opening_float or 0) + cash_sales + pay_in - pay_out, 2)
    return {
        "id": shift.id,
        "status": shift.status,
        "opened_by": _name(db, shift.opened_by),
        "opened_at": nepal.iso(shift.opened_at),
        "closed_by": _name(db, shift.closed_by),
        "closed_at": nepal.iso(shift.closed_at) if shift.closed_at else None,
        "opening_float": round(shift.opening_float or 0, 2),
        "bills": len(bills),
        "voided_bills": len(voided),
        "refunded_cash": round(refunded_cash, 2),
        "total_sales": round(sum(by_method.values()), 2),
        "discounts": round(discounts, 2),
        "by_method": [{"method": k, "label": PAYMENT_METHODS.get(k, k), "amount": v}
                      for k, v in sorted(by_method.items(), key=lambda kv: -kv[1])],
        "cash_sales": cash_sales,
        "pay_in": pay_in,
        "pay_out": pay_out,
        "movements": [{"id": m.id, "kind": m.kind, "amount": m.amount, "reason": m.reason,
                       "by": _name(db, m.user_id), "at": nepal.iso(m.created_at)} for m in moves],
        "expected_cash": shift.expected_cash if shift.status == "closed" else expected,
        "counted_cash": shift.counted_cash,
        "difference": shift.difference,
        "notes": shift.notes,
    }


@router.get("/current")
def current_shift(db: Session = Depends(get_db), current_user: User = Depends(_viewer)):
    shift = _current(db, ops.restaurant_id_of(current_user))
    return {"shift": shift_summary(db, shift) if shift else None}


@router.post("/open", status_code=201)
def open_shift(body: OpenShift, db: Session = Depends(get_db),
               current_user: User = Depends(_drawer_user)):
    rid = ops.restaurant_id_of(current_user)
    if body.opening_float < 0:
        raise HTTPException(status_code=400, detail="The opening float can't be negative")
    with db_transaction(db):
        ops.lock_restaurant(db, rid)
        if _current(db, rid):
            raise HTTPException(status_code=409, detail="The cash drawer is already open")
        shift = CashShift(restaurant_id=rid, opened_by=current_user.id,
                          opening_float=round(body.opening_float, 2),
                          notes=(body.notes or "").strip()[:500] or None)
        db.add(shift)
        db.flush()
        audit.record(db, current_user, "OPEN_DRAWER", "cash_shifts", shift.id,
                     {"opening_float": shift.opening_float})
        db.commit()
    return shift_summary(db, shift)


@router.post("/current/movement", status_code=201)
def cash_movement(body: Movement, db: Session = Depends(get_db),
                  current_user: User = Depends(_drawer_user)):
    rid = ops.restaurant_id_of(current_user)
    if body.kind not in ("in", "out"):
        raise HTTPException(status_code=400, detail="kind must be 'in' or 'out'")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Enter an amount above zero")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Say what the cash was for")
    shift = _current(db, rid)
    if not shift:
        raise HTTPException(status_code=400, detail="Open the cash drawer first")
    m = CashMovement(restaurant_id=rid, shift_id=shift.id, kind=body.kind,
                     amount=round(body.amount, 2), reason=body.reason.strip()[:200],
                     user_id=current_user.id)
    db.add(m)
    db.flush()
    audit.record(db, current_user, "CASH_IN" if body.kind == "in" else "CASH_OUT",
                 "cash_shifts", shift.id, {"amount": m.amount}, reason=m.reason)
    db.commit()
    return shift_summary(db, shift)


@router.post("/current/close")
def close_shift(body: CloseShift, db: Session = Depends(get_db),
                current_user: User = Depends(_drawer_user)):
    rid = ops.restaurant_id_of(current_user)
    if body.counted_cash < 0:
        raise HTTPException(status_code=400, detail="Counted cash can't be negative")
    with db_transaction(db):
        ops.lock_restaurant(db, rid)
        shift = _current(db, rid)
        if not shift:
            raise HTTPException(status_code=400, detail="The cash drawer isn't open")
        expected = shift_summary(db, shift)["expected_cash"]
        shift.status = "closed"
        shift.closed_by = current_user.id
        shift.closed_at = nepal.now()
        shift.expected_cash = expected
        shift.counted_cash = round(body.counted_cash, 2)
        shift.difference = round(shift.counted_cash - expected, 2)
        note = (body.notes or "").strip()
        if note:
            shift.notes = ((shift.notes + " · ") if shift.notes else "") + note
            shift.notes = shift.notes[:500]
        audit.record(db, current_user, "CLOSE_DRAWER", "cash_shifts", shift.id,
                     {"expected": expected, "counted": shift.counted_cash,
                      "difference": shift.difference})
        db.commit()
    return shift_summary(db, shift)


@router.get("")
def shift_history(limit: int = 30, db: Session = Depends(get_db),
                  current_user: User = Depends(_viewer)):
    rid = ops.restaurant_id_of(current_user)
    shifts = (db.query(CashShift).filter(CashShift.restaurant_id == rid)
                .order_by(CashShift.id.desc()).limit(max(1, min(limit, 200))).all())
    return [shift_summary(db, s) for s in shifts]


@router.get("/{shift_id}")
def get_shift(shift_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(_viewer)):
    return shift_summary(db, _get(db, shift_id, current_user))


def _get(db: Session, shift_id: int, user: User) -> CashShift:
    shift = db.query(CashShift).filter(CashShift.id == shift_id,
                                       CashShift.restaurant_id == ops.restaurant_id_of(user)).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift
