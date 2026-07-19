from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("phone", "restaurant_id", name="uq_customer_per_restaurant"),
    )

    id             = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name           = Column(String, nullable=False)
    phone          = Column(String, nullable=False)  # Primary identifier per restaurant
    email          = Column(String, nullable=True)
    total_visits   = Column(Integer, default=0)
    total_spent    = Column(Float, default=0.0)      # Lifetime spending in NPR
    loyalty_points = Column(Integer, default=0)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, server_default=func.now(), onupdate=func.now())
