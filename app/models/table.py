from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"
    __table_args__ = (
        UniqueConstraint("table_number", "restaurant_id", name="uq_table_per_restaurant"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    table_number  = Column(String, nullable=False)  # T1, T2, VIP-1
    capacity      = Column(Integer, nullable=False)
    status        = Column(String, default="free")  # free / occupied / reserved
    floor         = Column(String, nullable=True)   # Ground / First / Rooftop
    pos_x         = Column(Integer, default=0)
    pos_y         = Column(Integer, default=0)
    created_at    = Column(DateTime, server_default=func.now())
