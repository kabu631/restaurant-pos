from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class Restaurant(Base):
    __tablename__ = "restaurants"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String, nullable=False)
    slug       = Column(String, unique=True, nullable=False)   # login code, e.g. "spice-garden"
    phone      = Column(String, nullable=True)
    address    = Column(String, nullable=True)
    vat_number = Column(String, nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=nepal.now, server_default=func.now())
