from datetime import datetime
from app import db
from app.models.user import AuditLog


def log_action(action, performed_by_user_id=None, target_user_id=None, metadata=None, ip_address=None):
    entry = AuditLog(
        user_id=performed_by_user_id,
        action=action,
        target_user_id=target_user_id,
        metadata=metadata or {},
        ip_address=ip_address,
        performed_at=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry
