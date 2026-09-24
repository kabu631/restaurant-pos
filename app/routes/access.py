"""
Roles & permissions (admin edits what cashiers, waiters and kitchen may do) and the
staff activity log (who did what, when).
"""
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditTrail
from app.models.user import User
from app.routes.auth import require_admin
from app.services import audit
from app.services import order_ops as ops
from app.services.permissions import (DEFAULT_GRANTS, EDITABLE_ROLES, PERMISSIONS, ROLE_LABELS,
                                      discount_limit, role_grants, save_role_grants)
from app.services.restaurant_settings import set_setting
from app.utils import nepal

router = APIRouter(prefix="/api", tags=["access"])


class PermissionsUpdate(BaseModel):
    grants: Optional[Dict[str, List[str]]] = None
    max_discount_pct: Optional[float] = None


def _catalog(db: Session, rid: int) -> dict:
    grants = role_grants(db, rid)
    return {
        "permissions": [{"key": k, "label": v[0], "group": v[1], "help": v[2]}
                        for k, v in PERMISSIONS.items()],
        "roles": [{"key": r, "label": ROLE_LABELS[r], "grants": sorted(grants[r]),
                   "defaults": sorted(DEFAULT_GRANTS[r])} for r in EDITABLE_ROLES],
        "max_discount_pct": discount_limit(db, rid),
    }


@router.get("/permissions")
def get_permissions(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return _catalog(db, ops.restaurant_id_of(current_user))


@router.put("/permissions")
def update_permissions(body: PermissionsUpdate, db: Session = Depends(get_db),
                       current_user: User = Depends(require_admin)):
    rid = ops.restaurant_id_of(current_user)
    before = _catalog(db, rid)
    if body.grants is not None:
        unknown_roles = [r for r in body.grants if r not in EDITABLE_ROLES]
        if unknown_roles:
            raise HTTPException(status_code=400,
                                detail=f"Only {', '.join(EDITABLE_ROLES)} can be changed — admin can always do everything")
        merged = {r["key"]: r["grants"] for r in before["roles"]}
        merged.update(body.grants)
        save_role_grants(db, rid, merged)
    if body.max_discount_pct is not None:
        if not 0 <= body.max_discount_pct <= 100:
            raise HTTPException(status_code=400, detail="Discount limit must be between 0 and 100 %")
        set_setting(db, rid, "max_discount_pct", f"{body.max_discount_pct:g}")
    db.flush()
    after = _catalog(db, rid)
    audit.record(db, current_user, "PERMISSIONS", "app_settings", None,
                 {"roles": {r["key"]: r["grants"] for r in after["roles"]},
                  "max_discount_pct": after["max_discount_pct"]},
                 old={"roles": {r["key"]: r["grants"] for r in before["roles"]},
                      "max_discount_pct": before["max_discount_pct"]})
    db.commit()
    return after


# ── Activity log ──────────────────────────────────────────────────────────────

# action → (icon, category, sentence template)
ACTIONS = {
    "LOGIN":           ("🔑", "staff",   "logged in"),
    "OPEN_ORDER":      ("🧾", "orders",  "opened an order"),
    "SEND_KOT":        ("🔥", "orders",  "sent KOT to the kitchen"),
    "ACCEPT_KOT":      ("✅", "kitchen", "accepted a kitchen ticket"),
    "CANCEL_ORDER":    ("✖", "orders",  "cancelled an order"),
    "TRANSFER_ORDER":  ("↔", "orders",  "moved an order to another table"),
    "CREATE_BILL":     ("🧾", "billing", "created a bill"),
    "PAY_BILL":        ("💳", "billing", "took payment"),
    "PRINT_BILL":      ("🖨", "billing", "printed a bill"),
    "BILL_DISCOUNT":   ("🏷", "billing", "changed a bill's discount"),
    "VOID_BILL":       ("⛔", "billing", "voided a bill"),
    "OPEN_DRAWER":     ("💵", "cash",    "opened the cash drawer"),
    "CLOSE_DRAWER":    ("💵", "cash",    "closed the cash drawer"),
    "CASH_IN":         ("➕", "cash",    "put cash into the drawer"),
    "CASH_OUT":        ("➖", "cash",    "took cash out of the drawer"),
    "SOLD_OUT":        ("🚫", "menu",    "marked a dish sold out"),
    "BACK_ON_MENU":    ("🍽", "menu",    "put a dish back on the menu"),
    "PRICE_CHANGE":    ("💲", "menu",    "changed a price"),
    "CREATE_USER":     ("👤", "staff",   "added a staff member"),
    "UPDATE_USER":     ("👤", "staff",   "edited a staff member"),
    "DEACTIVATE_USER": ("🚷", "staff",   "deactivated a staff member"),
    "ACTIVATE_USER":   ("👤", "staff",   "re-activated a staff member"),
    "SIGN_OUT_USER":   ("🚪", "staff",   "signed a staff member out"),
    "RESET_PASSWORD":  ("🔒", "staff",   "reset a password"),
    "RESET_PIN":       ("🔒", "staff",   "reset a PIN"),
    "CHANGE_OWN_PIN":  ("🔒", "staff",   "changed their own PIN"),
    "CHANGE_OWN_PASSWORD": ("🔒", "staff", "changed their own password"),
    "PERMISSIONS":     ("🛡", "settings", "changed role permissions"),
    "SETTINGS":        ("⚙", "settings", "changed settings"),
}
SENSITIVE = {"VOID_BILL", "CANCEL_ORDER", "BILL_DISCOUNT", "PRICE_CHANGE", "CASH_OUT",
             "PERMISSIONS", "DEACTIVATE_USER", "RESET_PASSWORD"}


def _describe(row: AuditTrail, detail: dict, names: Dict[int, str]) -> str:
    icon, _, text = ACTIONS.get(row.action, ("•", "other", row.action.replace("_", " ").lower()))
    bits = []
    if detail.get("bill_number"):
        bits.append(f"bill {detail['bill_number']}")
    if detail.get("grand_total") is not None and row.action in ("PAY_BILL", "VOID_BILL", "CREATE_BILL"):
        bits.append(f"Rs {detail['grand_total']:,.2f}")
    if detail.get("table"):
        bits.append(f"table {detail['table']}")
    if detail.get("kot"):
        bits.append(f"KOT #{detail['kot']}")
    if detail.get("name"):
        bits.append(str(detail["name"]))
    if detail.get("amount") is not None and row.table_name == "cash_shifts":
        bits.append(f"Rs {detail['amount']:,.2f}")
    if detail.get("difference") is not None:
        d = detail["difference"]
        bits.append("cash matched" if abs(d) < 0.005 else f"{'over' if d > 0 else 'short'} Rs {abs(d):,.2f}")
    if detail.get("discount"):
        bits.append(f"discount Rs {detail['discount']:,.2f}")
    if detail.get("approved_by"):
        bits.append(f"approved by {detail['approved_by']}")
    if row.action == "PRICE_CHANGE" and detail.get("price") is not None:
        bits.append(f"→ Rs {detail['price']:,.2f}")
    if detail.get("method"):
        bits.append(f"with {detail['method'].upper() if detail['method'] == 'pin' else detail['method']}")
    if row.table_name == "users" and row.record_id and row.record_id != row.user_id:
        bits.append(names.get(row.record_id, f"user #{row.record_id}"))
    if detail.get("changed"):
        bits.append(", ".join(str(c).replace("_", " ") for c in detail["changed"][:4]))
    return f"{text}" + (f" — {' · '.join(bits)}" if bits else "")


@router.get("/activity")
def activity(
    day: Optional[date] = Query(None, description="Nepal date, default today"),
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    important: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rid = ops.restaurant_id_of(current_user)
    d = day or nepal.today()
    start = datetime(d.year, d.month, d.day)
    q = (db.query(AuditTrail)
           .filter(AuditTrail.restaurant_id == rid,
                   AuditTrail.created_at >= start,
                   AuditTrail.created_at < start + timedelta(days=1)))
    if user_id:
        q = q.filter(AuditTrail.user_id == user_id)
    if category:
        q = q.filter(AuditTrail.action.in_([a for a, v in ACTIONS.items() if v[1] == category]))
    if important:
        q = q.filter(AuditTrail.action.in_(SENSITIVE))
    rows = q.order_by(AuditTrail.id.desc()).limit(max(1, min(limit, 1000))).all()

    staff = db.query(User).filter(User.restaurant_id == rid).all()
    names = {u.id: u.full_name for u in staff}
    roles = {u.id: u.role for u in staff}
    out = []
    for r in rows:
        try:
            detail = json.loads(r.new_value) if r.new_value else {}
            if not isinstance(detail, dict):
                detail = {}
        except ValueError:
            detail = {}
        icon, cat, _ = ACTIONS.get(r.action, ("•", "other", ""))
        out.append({
            "id": r.id,
            "at": nepal.iso(r.created_at),
            "user_id": r.user_id,
            "user": names.get(r.user_id, "System"),
            "role": ROLE_LABELS.get(roles.get(r.user_id), ""),
            "action": r.action,
            "icon": icon,
            "category": cat,
            "important": r.action in SENSITIVE,
            "text": _describe(r, detail, names),
            "reason": r.reason,
            "ip": r.ip_address,
        })
    return {
        "day": d.isoformat(),
        "entries": out,
        "staff": [{"id": u.id, "name": u.full_name, "role": u.role} for u in
                  sorted(staff, key=lambda u: u.full_name)],
        "categories": sorted({v[1] for v in ACTIONS.values()}),
    }
