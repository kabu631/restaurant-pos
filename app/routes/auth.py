import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app.models.audit import AuditTrail
from app.models.user import User
from app.models.restaurant import Restaurant
from app.services.permissions import ROLE_LABELS, discount_limit, permissions_for
from app.utils import nepal
from app.utils.security import verify_password, create_access_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Where each role lands after signing in
HOME_PAGE = {
    "superadmin": "/admin",
    "admin": "/dashboard",
    "cashier": "/billing",      # the cashier's queue of tables ready to bill
    "waiter": "/tables",
    "kitchen": "/kitchen",
}


# --- Schemas ---

class LoginRequest(BaseModel):
    username: str
    password: str
    restaurant_code: Optional[str] = None   # blank/None = superadmin login

class PinLoginRequest(BaseModel):
    pin: str
    restaurant_code: str                    # always required for PIN login

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# --- Brute-force guard: 5 failures per key → locked for 60 s ---

_MAX_FAILURES = 5
_LOCK_SECONDS = 60
_failures: dict[str, tuple] = {}   # key → (failure count, locked-until monotonic time)
_failures_lock = threading.Lock()


def _check_locked(key: str):
    with _failures_lock:
        _, until = _failures.get(key, (0, 0.0))
        if until and time.monotonic() < until:
            wait = int(until - time.monotonic()) + 1
            raise HTTPException(status_code=429,
                                detail=f"Too many wrong attempts. Try again in {wait} seconds.")


def _record_failure(key: str):
    with _failures_lock:
        count, until = _failures.get(key, (0, 0.0))
        if until and time.monotonic() >= until:
            count = 0
        count += 1
        _failures[key] = (count, time.monotonic() + _LOCK_SECONDS if count >= _MAX_FAILURES else 0.0)


def _clear_failures(key: str):
    with _failures_lock:
        _failures.pop(key, None)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# --- Dependency: get current user from JWT ---

def token_from_request(request: Request) -> Optional[str]:
    """Bearer header first (API calls), then the login cookie (print pages, images)."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer ") and header[7:].strip():
        return header[7:].strip()
    return request.cookies.get("access_token") or None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if int(payload.get("sv", 0)) != (user.session_version or 0):
        # An admin signed this person out (or changed their password/role) — end the session now
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="You were signed out. Please log in again.")
    _touch(db, user)
    return user


def _touch(db: Session, user: User) -> None:
    """Remember when staff were last active (at most once a minute) for "online now"."""
    now = nepal.now()
    if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() > 60:
        user.last_seen_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()


def require_roles(*roles):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return checker


def require_superadmin(current_user: User = Depends(get_current_user)):
    if current_user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)):
    """Allow admin or superadmin only."""
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# --- Helper ---

def _user_dict(user: User, restaurant: Optional[Restaurant], db: Session) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "restaurant_id": user.restaurant_id,
        "restaurant_name": restaurant.name if restaurant else None,
        "restaurant_slug": restaurant.slug if restaurant else None,
        "home": HOME_PAGE.get(user.role, "/dashboard"),
        "fiscal_year": nepal.fiscal_year(),
        "permissions": sorted(permissions_for(db, user)),
        "discount_limit": discount_limit(db, user.restaurant_id),
        "has_pin": bool(user.pin),
    }


def within_shift(user: User, at=None) -> bool:
    """Login hours (Nepal time).  Empty = any time; admins are never limited.
    Handles overnight shifts such as 18:00–02:00."""
    if user.role in ("admin", "superadmin") or not (user.shift_start and user.shift_end):
        return True
    now = (at or nepal.now()).strftime("%H:%M")
    start, end = user.shift_start, user.shift_end
    return start <= now < end if start < end else (now >= start or now < end)


def _admit(db: Session, request: Request, user: User, how: str) -> None:
    if not within_shift(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Your login hours are {user.shift_start}–{user.shift_end}. "
                                   f"Ask your admin if you need to log in now.")
    user.last_login = user.last_seen_at = nepal.now()
    db.add(AuditTrail(restaurant_id=user.restaurant_id, user_id=user.id, action="LOGIN",
                      table_name="users", record_id=user.id,
                      new_value=f'{{"method": "{how}"}}', ip_address=_client_ip(request)))
    db.commit()


def _issue(response: Response, user: User, restaurant: Optional[Restaurant], db: Session) -> dict:
    token = create_access_token({"sub": user.id, "role": user.role, "rid": user.restaurant_id,
                                 "sv": user.session_version or 0})
    # HttpOnly cookie lets print pages (/receipt, /kot-print) authenticate without a token in the URL
    response.set_cookie("access_token", token, httponly=True, samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user, restaurant, db)}


# --- Endpoints ---

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    restaurant: Optional[Restaurant] = None
    code = (body.restaurant_code or "").strip().lower()
    guard_key = f"pw:{_client_ip(request)}:{code}:{body.username.strip().lower()}"
    _check_locked(guard_key)

    if code:
        restaurant = db.query(Restaurant).filter(Restaurant.slug == code).first()
        if not restaurant:
            raise HTTPException(status_code=404, detail=f"No restaurant with code \"{code}\". Use the short login code (like sample or demo), not the restaurant name.")
        if not restaurant.is_active:
            raise HTTPException(status_code=403, detail="This restaurant account is inactive.")

        user = db.query(User).filter(
            User.username == body.username.strip(),
            User.restaurant_id == restaurant.id,
        ).first()
    else:
        # Superadmin login — no restaurant code
        user = db.query(User).filter(
            User.username == body.username.strip(),
            User.role == "superadmin",
            User.restaurant_id.is_(None),
        ).first()

    if not user or not verify_password(body.password, user.password_hash):
        _record_failure(guard_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    _clear_failures(guard_key)
    _admit(db, request, user, "password")
    return _issue(response, user, restaurant, db)


@router.post("/pin-login", response_model=TokenResponse)
def pin_login(body: PinLoginRequest, request: Request, response: Response,
              db: Session = Depends(get_db)):
    if not body.pin or len(body.pin) != 4 or not body.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be 4 digits")

    code = body.restaurant_code.strip().lower()
    guard_key = f"pin:{_client_ip(request)}:{code}"
    _check_locked(guard_key)

    restaurant = db.query(Restaurant).filter(Restaurant.slug == code).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail=f"No restaurant with code \"{code}\". Use the short login code (like sample or demo), not the restaurant name.")
    if not restaurant.is_active:
        raise HTTPException(status_code=403, detail="This restaurant account is inactive.")

    user = db.query(User).filter(
        User.pin == body.pin,
        User.restaurant_id == restaurant.id,
        User.is_active.is_(True),
    ).first()
    if not user:
        _record_failure(guard_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

    _clear_failures(guard_key)
    _admit(db, request, user, "pin")
    return _issue(response, user, restaurant, db)


@router.post("/logout")
def logout():
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("access_token")
    return response


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    restaurant = None
    if current_user.restaurant_id:
        restaurant = db.query(Restaurant).filter(Restaurant.id == current_user.restaurant_id).first()
    return _user_dict(current_user, restaurant, db)


class ChangePin(BaseModel):
    current_password: str
    new_pin: str


@router.post("/change-pin")
def change_own_pin(body: ChangePin, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Any staff member can change their own quick-login PIN (password required)."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if not (body.new_pin.isdigit() and len(body.new_pin) == 4):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    clash = db.query(User).filter(User.restaurant_id == current_user.restaurant_id,
                                  User.pin == body.new_pin, User.id != current_user.id).first()
    if clash:
        raise HTTPException(status_code=409, detail="That PIN is already used by another staff member")
    current_user.pin = body.new_pin
    db.add(AuditTrail(restaurant_id=current_user.restaurant_id, user_id=current_user.id,
                      action="CHANGE_OWN_PIN", table_name="users", record_id=current_user.id))
    db.commit()
    return {"ok": True}
