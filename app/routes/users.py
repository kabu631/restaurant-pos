import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, db_transaction

_log = logging.getLogger(__name__)
from app.models.user import User
from app.models.audit import AuditTrail
from app.routes.auth import require_admin
from app.utils.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

STAFF_ROLES = {"admin", "cashier", "waiter", "kitchen"}


# --- Schemas ---

class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str
    pin: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    pin: Optional[str] = None

class ResetPassword(BaseModel):
    new_password: str

class ResetPin(BaseModel):
    new_pin: str


# --- Helpers ---

def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "has_pin": bool(u.pin),
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }

def _get_tenant_user(user_id: int, actor: User, db: Session) -> User:
    q = db.query(User).filter(User.id == user_id, User.role != "superadmin")
    if actor.role != "superadmin":
        q = q.filter(User.restaurant_id == actor.restaurant_id)
    user = q.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

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
    return [_user_out(u) for u in q.order_by(User.full_name).all()]


@router.post("", status_code=201)
def create_user(
    body: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose: {', '.join(sorted(STAFF_ROLES))}")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if body.pin and (not body.pin.isdigit() or len(body.pin) != 4):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")

    existing = db.query(User).filter(
        User.username == body.username,
        User.restaurant_id == current_user.restaurant_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken in this restaurant")

    with db_transaction(db):
        user = User(
            restaurant_id=current_user.restaurant_id,
            username=body.username,
            password_hash=hash_password(body.password),
            full_name=body.full_name,
            role=body.role,
            is_active=True,
            pin=body.pin or None,
        )
        db.add(user)
        db.flush()
        _audit(db, current_user, "CREATE_USER", user.id,
               {"username": body.username, "role": body.role})
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
    if body.pin is not None and body.pin != "" and (not body.pin.isdigit() or len(body.pin) != 4):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    if body.username and body.username != user.username:
        dup = db.query(User).filter(
            User.username == body.username,
            User.restaurant_id == current_user.restaurant_id,
            User.id != user_id,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail="Username already taken")

    old = {"username": user.username, "role": user.role, "full_name": user.full_name}
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.username is not None:
        user.username = body.username
    if body.role is not None:
        user.role = body.role
    if body.pin is not None:
        user.pin = body.pin if body.pin else None

    _audit(db, current_user, "UPDATE_USER", user.id, {"old": old, "new": body.model_dump(exclude_none=True)})
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
    user.is_active = False
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
    _audit(db, current_user, "RESET_PASSWORD", user.id)
    db.commit()
    return {"ok": True}
