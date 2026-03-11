import csv
import io
import json
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.models.user import User, AuditLog
from app.services import audit_logger


def _user_to_dict(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "address": user.address,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _audit_log_to_dict(log: AuditLog) -> Dict[str, Any]:
    return {
        "id": log.id,
        "event_type": log.event_type,
        "description": log.description,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def build_export_package(db: Session, user_id: int) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        return None

    logs = audit_logger.get_audit_logs_for_user(db, user_id)

    package = {
        "exported_at": datetime.utcnow().isoformat(),
        "user": _user_to_dict(user),
        "audit_logs": [_audit_log_to_dict(l) for l in logs],
    }
    return package


def export_as_json(db: Session, user_id: int) -> str:
    package = build_export_package(db, user_id)
    if package is None:
        return None
    return json.dumps(package, indent=2)


def export_as_csv(db: Session, user_id: int) -> str:
    package = build_export_package(db, user_id)
    if package is None:
        return None

    output = io.StringIO()

    # User section
    writer = csv.writer(output)
    writer.writerow(["=== USER DATA ==="])
    user_data = package["user"]
    writer.writerow(list(user_data.keys()))
    writer.writerow(list(user_data.values()))
    writer.writerow([])

    # Audit logs section
    writer.writerow(["=== AUDIT LOGS ==="])
    if package["audit_logs"]:
        writer.writerow(list(package["audit_logs"][0].keys()))
        for log in package["audit_logs"]:
            writer.writerow(list(log.values()))

    return output.getvalue()


def irreversibly_delete_user(
    db: Session,
    user_id: int,
    actor_id: int,
    ip_address: str = None,
    user_agent: str = None,
) -> bool:
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        return False

    audit_logger.log_event(
        db=db,
        event_type=audit_logger.EVENT_DATA_DELETE_INITIATED,
        user_id=user_id,
        actor_id=actor_id,
        description=f"Deletion initiated for user {user_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        extra={"email": user.email, "username": user.username},
    )

    # Scrub PII fields irreversibly
    user.email = f"deleted_{user_id}@deleted.invalid"
    user.username = f"deleted_{user_id}"
    user.full_name = None
    user.phone = None
    user.address = None
    user.hashed_password = ""
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()

    db.add(user)
    db.commit()

    audit_logger.log_event(
        db=db,
        event_type=audit_logger.EVENT_DATA_DELETE_COMPLETED,
        user_id=None,  # PII link severed intentionally
        actor_id=actor_id,
        description=f"Deletion completed for original user_id={user_id}",
        ip_address=ip_address,
        user_agent=user_agent,
        extra={"original_user_id": user_id},
    )

    return True
