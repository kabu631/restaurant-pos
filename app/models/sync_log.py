from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)        # INSERT / UPDATE / DELETE
    data_snapshot = Column(Text, nullable=True)    # Full JSON of the record
    is_synced = Column(Boolean, default=False)
    synced_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=nepal.now, server_default=func.now())
