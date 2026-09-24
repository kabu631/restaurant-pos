from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal

# Where a category's items are prepared.  "none" = served straight from the
# counter (bottled drinks, etc.) and never printed on a kitchen ticket.
STATIONS = ("kitchen", "bar", "none")


class Category(Base):
    __tablename__ = "categories"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name          = Column(String, nullable=False)
    display_order = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    station       = Column(String, default="kitchen")  # kitchen / bar / none
    created_at    = Column(DateTime, default=nepal.now, server_default=func.now())


class MenuItem(Base):
    __tablename__ = "menu_items"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id     = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    category_id       = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name              = Column(String, nullable=False)
    name_np           = Column(String, nullable=True)       # Nepali name for QR menu
    price             = Column(Float, nullable=False)       # Selling price in NPR
    variant_type      = Column(String, nullable=True)       # half/full, S/M/L, or NULL
    description       = Column(Text, nullable=True)
    is_vat_applicable = Column(Boolean, default=True)
    is_available      = Column(Boolean, default=True)
    image_path        = Column(String, nullable=True)
    display_order     = Column(Integer, default=0)
    created_at        = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at        = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)
