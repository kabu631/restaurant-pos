from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class CashShift(Base):
    """One cash-drawer session: opened with a float, closed with the counted cash."""
    __tablename__ = "cash_shifts"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    status         = Column(String(10), default="open", nullable=False)   # open / closed
    opened_by      = Column(Integer, ForeignKey("users.id"), nullable=False)
    opened_at      = Column(DateTime, default=nepal.now, server_default=func.now())
    opening_float  = Column(Float, default=0.0, nullable=False)
    closed_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at      = Column(DateTime, nullable=True)
    expected_cash  = Column(Float, nullable=True)     # float + cash sales + pay-ins − pay-outs
    counted_cash   = Column(Float, nullable=True)
    difference     = Column(Float, nullable=True)     # counted − expected (negative = short)
    notes          = Column(String(500), nullable=True)


class CashMovement(Base):
    """Cash put into or taken out of the drawer that isn't a sale (petty cash, bank drop)."""
    __tablename__ = "cash_movements"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    shift_id      = Column(Integer, ForeignKey("cash_shifts.id"), nullable=False, index=True)
    kind          = Column(String(5), nullable=False)          # in / out
    amount        = Column(Float, nullable=False)
    reason        = Column(String(200), nullable=False)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=nepal.now, server_default=func.now())
