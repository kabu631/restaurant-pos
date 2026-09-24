from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class Ingredient(Base):
    __tablename__ = "ingredients"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id     = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name              = Column(String, nullable=False)
    unit              = Column(String, nullable=False)      # kg / litre / piece / gram
    current_stock     = Column(Float, default=0.0)
    minimum_stock     = Column(Float, default=0.0)         # Low-stock alert threshold
    cost_per_unit     = Column(Float, default=0.0)         # Purchase cost in NPR
    supplier_name     = Column(String, nullable=True)
    last_purchased_at = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at        = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)


class StockPurchase(Base):
    __tablename__ = "stock_purchases"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    quantity      = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False)
    total_cost    = Column(Float, nullable=False)
    supplier_name = Column(String, nullable=True)
    purchased_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    purchased_at  = Column(DateTime, default=nepal.now, server_default=func.now())


class AppSettings(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("key", "restaurant_id", name="uq_setting_per_restaurant"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    key           = Column(String, nullable=False)
    value         = Column(Text, nullable=True)        # can hold an uploaded QR image
    description   = Column(Text, nullable=True)
