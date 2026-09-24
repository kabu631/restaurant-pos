"""
Role-based access control.

Every restaurant has one boss — the **admin** — who can do everything, including
managing staff and changing what the other roles may do.  The other roles get a
set of permissions; these are the defaults, and an admin can adjust them per
restaurant on Settings → Roles & permissions (stored as AppSettings
"role_permissions").

Staff management, menu/table/inventory set-up and settings always stay admin-only.
"""
import json
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.restaurant_settings import as_float, get_setting, set_setting

# key → (label, group, what it allows)
PERMISSIONS: dict[str, tuple[str, str, str]] = {
    "orders.take":       ("Take orders", "Orders",
                          "Open tables and takeaway orders, add dishes, send them to the kitchen"),
    "orders.cancel":     ("Cancel orders", "Orders",
                          "Cancel an order before anything has gone to the kitchen"),
    "orders.transfer":   ("Move tables", "Orders", "Move an open order to another table"),
    "orders.serve":      ("Serve food", "Orders", "Mark dishes the kitchen has finished as served"),
    "kitchen.manage":    ("Run the kitchen screen", "Kitchen",
                          "Accept new orders and mark them ready / served on the kitchen display"),
    "menu.availability": ("Mark dishes sold out", "Kitchen",
                          "Switch a dish off (and back on) when it runs out"),
    "billing.pay":       ("Take payment & print bills", "Billing",
                          "Settle a table's bill, print the final bill, reprint receipts"),
    "billing.discount":  ("Give discounts", "Billing",
                          "Discounts up to the limit below; more needs the admin's PIN"),
    "billing.void":      ("Void paid bills (refund)", "Billing",
                          "Cancel a paid bill; without this the admin must approve with their PIN"),
    "cash.shift":        ("Open & close the cash drawer", "Billing",
                          "Start a shift with the float and close it with the counted cash"),
    "bookings.manage":   ("Manage bookings", "Front of house",
                          "Book tables, seat guests, mark no-shows"),
    "reports.view":      ("See sales reports", "Management",
                          "Sales, VAT and staff reports, and CSV exports"),
}

# Roles whose permissions the admin can change
EDITABLE_ROLES = ("cashier", "waiter", "kitchen")
ROLE_LABELS = {"admin": "Admin (owner/manager)", "cashier": "Cashier", "waiter": "Waiter",
               "kitchen": "Kitchen", "superadmin": "Platform admin"}

DEFAULT_GRANTS: dict[str, set[str]] = {
    # Waiters look after tables: take orders, serve, bookings
    "waiter":  {"orders.take", "orders.cancel", "orders.transfer", "orders.serve", "bookings.manage"},
    # Cashiers bill and take money; they can also ring up counter/takeaway orders
    "cashier": {"orders.take", "orders.cancel", "orders.transfer", "orders.serve",
                "billing.pay", "billing.discount", "cash.shift", "bookings.manage", "reports.view"},
    # The kitchen accepts and prepares orders, and says when a dish runs out
    "kitchen": {"kitchen.manage", "menu.availability"},
}

DEFAULT_DISCOUNT_LIMIT = 10.0     # % a non-admin may give without the admin's PIN
_SETTING_KEY = "role_permissions"


def role_grants(db: Session, restaurant_id: Optional[int]) -> dict[str, set[str]]:
    """Effective permissions for each editable role in this restaurant."""
    grants = {role: set(perms) for role, perms in DEFAULT_GRANTS.items()}
    if not restaurant_id:
        return grants
    raw = get_setting(db, restaurant_id, _SETTING_KEY)
    if raw:
        try:
            saved = json.loads(raw)
            for role in EDITABLE_ROLES:
                if isinstance(saved.get(role), list):
                    grants[role] = {p for p in saved[role] if p in PERMISSIONS}
        except (ValueError, AttributeError):
            pass    # corrupt setting → fall back to defaults
    return grants


def save_role_grants(db: Session, restaurant_id: int, grants: dict[str, Iterable[str]]) -> None:
    clean = {}
    for role in EDITABLE_ROLES:
        perms = grants.get(role, DEFAULT_GRANTS[role])
        unknown = [p for p in perms if p not in PERMISSIONS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown permission(s): {unknown}")
        clean[role] = sorted(set(perms))
    set_setting(db, restaurant_id, _SETTING_KEY, json.dumps(clean))


def permissions_for(db: Session, user: User) -> set[str]:
    if user.role in ("admin", "superadmin"):
        return set(PERMISSIONS)
    return role_grants(db, user.restaurant_id).get(user.role, set())


def has_perm(db: Session, user: User, *keys: str) -> bool:
    perms = permissions_for(db, user)
    return any(k in perms for k in keys)


def discount_limit(db: Session, restaurant_id: Optional[int]) -> float:
    if not restaurant_id:
        return DEFAULT_DISCOUNT_LIMIT
    return as_float(get_setting(db, restaurant_id, "max_discount_pct"), DEFAULT_DISCOUNT_LIMIT)


def denied(user: User, *keys: str) -> HTTPException:
    what = " / ".join(PERMISSIONS[k][0].lower() for k in keys if k in PERMISSIONS)
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Your role ({ROLE_LABELS.get(user.role, user.role)}) isn't allowed to {what}. "
               f"Ask your admin if you need this.",
    )


def require_perm(*keys: str):
    """FastAPI dependency: the signed-in user needs at least one of these permissions."""
    from app.routes.auth import get_current_user   # avoid a circular import at load time

    def checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not has_perm(db, user, *keys):
            raise denied(user, *keys)
        return user
    return checker


# ── Admin approval ("manager override") ─────────────────────────────────────────

def verify_override(db: Session, restaurant_id: int, pin: Optional[str]) -> User:
    """The admin types their PIN on the cashier's screen to approve one action."""
    if not pin or not str(pin).isdigit():
        raise HTTPException(status_code=403, detail="Admin approval needed",
                            headers={"X-Needs-Override": "1"})
    approver = db.query(User).filter(
        User.restaurant_id == restaurant_id,
        User.role == "admin",
        User.is_active.is_(True),
        User.pin == str(pin),
    ).first()
    if not approver:
        raise HTTPException(status_code=403, detail="That isn't an admin PIN",
                            headers={"X-Needs-Override": "1"})
    return approver
