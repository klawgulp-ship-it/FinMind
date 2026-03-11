import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.user import AuditLog


EVENT_DATA_EXPORT = "DATA_EXPORT"
EVENT_DATA_DELETE_INITIATED = "DATA_DELETE_INITIATED"
EVENT_DATA_DELETE_COMPLETED = "DATA_DELETE_COMPLETED"
EVENT_LOGIN = "LOGIN"
EVENT_LOGOUT = "LOGOUT"
EVENT_PASSWORD_CHANGE = "PASSWORD_CHANGE"


def log_event(
    db: Session,
    event_type: str,
    user_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        actor_id=actor_id,
        event_type=event_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_=json.dumps(extra) if extra else None,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_audit_logs_for_user(db: Session, user_id: int):
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
