from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)        # CREATE/UPDATE/DELETE/PRINT/LOGIN/LOGOUT/VOID
    table_name = Column(String, nullable=False)    # Which table was affected
    record_id = Column(Integer, nullable=True)     # ID of the affected record
    old_value = Column(String, nullable=True)      # JSON of previous values
    new_value = Column(String, nullable=True)      # JSON of new values
    ip_address = Column(String, nullable=True)
    reason = Column(String, nullable=True)         # Required for edits/voids (IRD)
    created_at = Column(DateTime, server_default=func.now())
