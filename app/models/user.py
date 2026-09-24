from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", "restaurant_id", name="uq_user_per_restaurant"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)  # NULL = superadmin
    username      = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name     = Column(String, nullable=False)
    role          = Column(String, nullable=False)  # superadmin/admin/cashier/waiter/kitchen
    is_active     = Column(Boolean, default=True)
    pin           = Column(String, nullable=True)   # 4-digit quick login PIN
    last_login    = Column(DateTime, nullable=True)
    last_seen_at  = Column(DateTime, nullable=True)  # last request — "online now" on the Staff page
    # Bumped to end every open session at once (sign out everywhere, deactivation, password reset)
    session_version = Column(Integer, default=0, nullable=False, server_default="0")
    # Optional login hours in Nepal time, "HH:MM"; both empty = any time. Admins are never limited.
    shift_start   = Column(String(5), nullable=True)
    shift_end     = Column(String(5), nullable=True)
    created_at    = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at    = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)
