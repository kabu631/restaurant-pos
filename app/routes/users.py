import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, db_transaction

_log = logging.getLogger(__name__)
from app.models.user import User
from app.models.audit import AuditTrail
from app.routes.auth import HOME_PAGE, require_admin, within_shift
from app.services.permissions import ROLE_LABELS, role_grants
from app.utils import nepal
from app.utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

STAFF_ROLES = {"admin", "cashier", "waiter", "kitchen"}
ONLINE_SECONDS = 5 * 60          # seen within the last 5 minutes = "online now"
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# --- Schemas ---

class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str
    pin: Optional[str] = None
    shift_start: Optional[str] = None      # "HH:MM" — login hours; empty = any time
    shift_end: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    pin: Optional[str] = None
    shift_start: Optional[str] = None      # "" clears login hours
    shift_end: Optional[str] = None

class ResetPassword(BaseModel):
    new_password: str

class ResetPin(BaseModel):
    new_pin: str


# --- Helpers ---

def _user_out(u: User, grants: Optional[dict] = None) -> dict:
    now = nepal.now()
    online = bool(u.is_active and u.last_seen_at
                  and (now - u.last_seen_at).total_seconds() < ONLINE_SECONDS)
    out = {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "role_label": ROLE_LABELS.get(u.role, u.role),
        "is_active": u.is_active,
        "has_pin": bool(u.pin),
        "shift_start": u.shift_start,
        "shift_end": u.shift_end,
        "can_login_now": within_shift(u),
        "online": online,
        "home": HOME_PAGE.get(u.role, "/dashboard"),
        "last_login": nepal.iso(u.last_login) if u.last_login else None,
        "last_seen_at": nepal.iso(u.last_seen_at) if u.last_seen_at else None,
        "created_at": nepal.iso(u.created_at) if u.created_at else None,
    }
    if grants is not None:
        out["permissions"] = sorted(grants.get(u.role, [])) if u.role != "admin" else ["*"]
    return out

def _get_tenant_user(user_id: int, actor: User, db: Session) -> User:
    q = db.query(User).filter(User.id == user_id, User.role != "superadmin")
    if actor.role != "superadmin":
        q = q.filter(User.restaurant_id == actor.restaurant_id)
    user = q.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def _check_pin_free(db: Session, restaurant_id, pin: str, exclude_user_id: int = None):
    """PIN login finds the user by PIN alone, so PINs must be unique per restaurant."""
    q = db.query(User).filter(User.restaurant_id == restaurant_id, User.pin == pin)
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    if q.first():
        raise HTTPException(status_code=409, detail="That PIN is already used by another staff member")

def _check_shift(start: Optional[str], end: Optional[str]) -> tuple:
    start, end = (start or "").strip() or None, (end or "").strip() or None
    if bool(start) != bool(end):
        raise HTTPException(status_code=400, detail="Set both a start and an end time, or neither")
    for t in (start, end):
        if t and not _HHMM.match(t):
            raise HTTPException(status_code=400, detail="Times must look like 09:30 (24-hour)")
    if start and start == end:
        raise HTTPException(status_code=400, detail="Start and end time can't be the same")
    return start, end

def _other_active_admins(db: Session, user: User) -> int:
    return db.query(User).filter(User.restaurant_id == user.restaurant_id, User.role == "admin",
                                 User.is_active.is_(True), User.id != user.id).count()

def _sign_out(user: User) -> None:
    """Invalidate every token this person holds — they must log in again."""
    user.session_version = (user.session_version or 0) + 1

def _audit(db: Session, actor: User, action: str, target_id: int, detail: dict = None):
    db.add(AuditTrail(
        restaurant_id=actor.restaurant_id,
        user_id=actor.id,
        action=action,
        table_name="users",
        record_id=target_id,
        new_value=json.dumps(detail) if detail else None,
    ))


# --- Endpoints ---

@router.get("")
def list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.role != "superadmin")
    if current_user.role != "superadmin":
        q = q.filter(User.restaurant_id == current_user.restaurant_id)
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    grants = role_grants(db, current_user.restaurant_id)
    return [_user_out(u, grants) for u in q.order_by(User.full_name).all()]


@router.post("", status_code=201)
def create_user(
    body: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose: {', '.join(sorted(STAFF_ROLES))}")
    if not body.full_name.strip() or not body.username.strip():
        raise HTTPException(status_code=400, detail="Name and username are required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if body.pin and (not body.pin.isdigit() or len(body.pin) != 4):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    if body.pin:
        _check_pin_free(db, current_user.restaurant_id, body.pin)
    shift_start, shift_end = _check_shift(body.shift_start, body.shift_end)

    existing = db.query(User).filter(
        User.username == body.username.strip(),
        User.restaurant_id == current_user.restaurant_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken in this restaurant")

    with db_transaction(db):
        user = User(
            restaurant_id=current_user.restaurant_id,
            username=body.username.strip(),
            password_hash=hash_password(body.password),
            full_name=body.full_name.strip(),
            role=body.role,
            is_active=True,
            pin=body.pin or None,
            shift_start=shift_start,
            shift_end=shift_end,
        )
        db.add(user)
        db.flush()
        _audit(db, current_user, "CREATE_USER", user.id,
               {"username": user.username, "role": body.role})
        db.commit()
    return _user_out(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_tenant_user(user_id, current_user, db)

    if body.role and body.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose: {', '.join(sorted(STAFF_ROLES))}")
    if body.role and body.role != "admin" and user.role == "admin" and _other_active_admins(db, user) == 0:
        raise HTTPException(status_code=400,
                            detail="This is the only admin — make someone else admin first")
    if body.pin is not None and body.pin != "" and (not body.pin.isdigit() or len(body.pin) != 4):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    if body.pin:
        _check_pin_free(db, user.restaurant_id, body.pin, exclude_user_id=user.id)
    if body.username and body.username != user.username:
        dup = db.query(User).filter(
            User.username == body.username,
            User.restaurant_id == current_user.restaurant_id,
            User.id != user_id,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail="Username already taken")
    shift_given = body.shift_start is not None or body.shift_end is not None
    if shift_given:
        shift_start, shift_end = _check_shift(
            body.shift_start if body.shift_start is not None else user.shift_start,
            body.shift_end if body.shift_end is not None else user.shift_end)

    old = {"username": user.username, "role": user.role, "full_name": user.full_name,
           "shift": [user.shift_start, user.shift_end]}
    if body.full_name is not None:
        user.full_name = body.full_name.strip() or user.full_name
    if body.username is not None:
        user.username = body.username.strip() or user.username
    if body.role is not None and body.role != user.role:
        user.role = body.role
        _sign_out(user)     # new role, new permissions — start a fresh session
    if body.pin is not None:
        user.pin = body.pin if body.pin else None
    if shift_given:
        user.shift_start, user.shift_end = shift_start, shift_end

    new = body.model_dump(exclude_none=True)
    new.pop("pin", None)    # never write PINs to the audit trail
    _audit(db, current_user, "UPDATE_USER", user.id, {"old": old, "new": new})
    db.commit()
    return _user_out(user)


@router.patch("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user = _get_tenant_user(user_id, current_user, db)
    if user.role == "admin" and _other_active_admins(db, user) == 0:
        raise HTTPException(status_code=400, detail="Can't deactivate the only admin")
    user.is_active = False
    _sign_out(user)
    _audit(db, current_user, "DEACTIVATE_USER", user.id)
    db.commit()
    return _user_out(user)


@router.patch("/{user_id}/activate")
def activate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_tenant_user(user_id, current_user, db)
    user.is_active = True
    _audit(db, current_user, "ACTIVATE_USER", user.id)
    db.commit()
    return _user_out(user)


@router.post("/{user_id}/sign-out")
def sign_out_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Sign this person out on every phone/tablet/PC right away (lost phone, end of shift)."""
    user = _get_tenant_user(user_id, current_user, db)
    _sign_out(user)
    user.last_seen_at = None
    _audit(db, current_user, "SIGN_OUT_USER", user.id)
    db.commit()
    return {"ok": True}


@router.patch("/{user_id}/reset-pin")
def reset_pin(
    user_id: int,
    body: ResetPin,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not body.new_pin.isdigit() or len(body.new_pin) != 4:
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    user = _get_tenant_user(user_id, current_user, db)
    _check_pin_free(db, user.restaurant_id, body.new_pin, exclude_user_id=user.id)
    user.pin = body.new_pin
    _audit(db, current_user, "RESET_PIN", user.id)
    db.commit()
    return {"ok": True}


@router.patch("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: ResetPassword,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = _get_tenant_user(user_id, current_user, db)
    user.password_hash = hash_password(body.new_password)
    if user.id != current_user.id:
        _sign_out(user)     # anyone using the old password is logged out
    _audit(db, current_user, "RESET_PASSWORD", user.id)
    db.commit()
    return {"ok": True}
