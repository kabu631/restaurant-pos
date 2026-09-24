from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class Order(Base):
    __tablename__ = "orders"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    table_id      = Column(Integer, ForeignKey("restaurant_tables.id"), nullable=True)
    order_type    = Column(String, nullable=False)   # dine_in / takeaway / delivery
    status        = Column(String, default="active") # active / completed / cancelled
    waiter_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    customer_name  = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)
    delivery_address = Column(Text, nullable=True)
    guests        = Column(Integer, nullable=True)   # covers seated at the table
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at    = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)


class OrderItem(Base):
    __tablename__ = "order_items"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    order_id     = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    quantity     = Column(Integer, nullable=False, default=1)
    unit_price   = Column(Float, nullable=False)      # Price at time of order
    notes        = Column(String, nullable=True)      # e.g. "no spice"
    kot_status   = Column(String, default="pending")  # pending/sent/preparing/ready/served/void
    kot_number   = Column(Integer, nullable=True)     # daily ticket number, per restaurant
    kot_sent_at  = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=nepal.now, server_default=func.now())
