from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.restaurant import Restaurant
from app.utils.security import verify_password, create_access_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


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


# --- Dependency: get current user from JWT ---

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token") or (
        request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
    )
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


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

def _user_dict(user: User, restaurant: Optional[Restaurant]) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "restaurant_id": user.restaurant_id,
        "restaurant_name": restaurant.name if restaurant else None,
        "restaurant_slug": restaurant.slug if restaurant else None,
    }


# --- Endpoints ---

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    restaurant: Optional[Restaurant] = None

    if body.restaurant_code:
        restaurant = db.query(Restaurant).filter(
            Restaurant.slug == body.restaurant_code.strip().lower()
        ).first()
        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant not found. Check your restaurant code.")
        if not restaurant.is_active:
            raise HTTPException(status_code=403, detail="This restaurant account is inactive.")

        user = db.query(User).filter(
            User.username == body.username,
            User.restaurant_id == restaurant.id,
        ).first()
    else:
        # Superadmin login — no restaurant code
        user = db.query(User).filter(
            User.username == body.username,
            User.role == "superadmin",
            User.restaurant_id.is_(None),
        ).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": user.id, "role": user.role, "rid": user.restaurant_id})
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user, restaurant)}


@router.post("/pin-login", response_model=TokenResponse)
def pin_login(body: PinLoginRequest, db: Session = Depends(get_db)):
    if not body.pin or len(body.pin) != 4:
        raise HTTPException(status_code=400, detail="PIN must be 4 digits")

    restaurant = db.query(Restaurant).filter(
        Restaurant.slug == body.restaurant_code.strip().lower()
    ).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not restaurant.is_active:
        raise HTTPException(status_code=403, detail="This restaurant account is inactive.")

    user = db.query(User).filter(
        User.pin == body.pin,
        User.restaurant_id == restaurant.id,
        User.is_active.is_(True),
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": user.id, "role": user.role, "rid": user.restaurant_id})
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user, restaurant)}


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
    return _user_dict(current_user, restaurant)
