"""Append-only audit trail (IRD): who did what, to which record, and why."""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditTrail
from app.models.user import User


def record(db: Session, user: Optional[User], action: str, table_name: str,
           record_id: Optional[int], detail: Optional[dict] = None,
           reason: Optional[str] = None, old: Optional[dict] = None) -> None:
    db.add(AuditTrail(
        restaurant_id=user.restaurant_id if user else None,
        user_id=user.id if user else None,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_value=json.dumps(old, default=str) if old else None,
        new_value=json.dumps(detail, default=str) if detail else None,
        reason=(reason or "").strip()[:500] or None,
    ))
