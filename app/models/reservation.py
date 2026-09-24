from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class Reservation(Base):
    __tablename__ = "reservations"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    table_id       = Column(Integer, ForeignKey("restaurant_tables.id"), nullable=True)  # NULL = not yet assigned
    customer_name  = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)
    party_size     = Column(Integer, nullable=False, default=2)
    reserved_for   = Column(DateTime, nullable=False)          # Nepal time
    duration_min   = Column(Integer, default=90)               # how long the table is held
    status         = Column(String, default="booked")          # booked / seated / cancelled / no_show
    notes          = Column(Text, nullable=True)               # birthday, high chair, ...
    order_id       = Column(Integer, ForeignKey("orders.id"), nullable=True)  # set when seated
    created_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at     = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at     = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)
