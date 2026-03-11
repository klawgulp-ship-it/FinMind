import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.dependencies import get_current_user

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _log(db: Session, user_id: int, action: str, detail: str = None, ip: str = None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        detail=detail,
        ip_address=ip,
    )
    db.add(entry)
    db.commit()


@router.post("/export")
def export_user_data(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a ZIP package containing all personal data for the current user."""
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": getattr(current_user, "username", None),
        "created_at": str(getattr(current_user, "created_at", "")),
    }

    audit_entries = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    audit_data = [
        {
            "action": e.action,
            "detail": e.detail,
            "ip_address": e.ip_address,
            "created_at": str(e.created_at),
        }
        for e in audit_entries
    ]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("profile.json", json.dumps(user_data, indent=2))
        zf.writestr("audit_log.json", json.dumps(audit_data, indent=2))
    zip_buffer.seek(0)

    _log(
        db,
        user_id=current_user.id,
        action="DATA_EXPORT",
        detail="User requested personal data export.",
        ip=request.client.host if request.client else None,
    )

    filename = f"pii_export_{current_user.id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/delete", status_code=status.HTTP_200_OK)
def delete_user_data(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Irreversibly delete all personal data for the current user."""
    user_id = current_user.id

    _log(
        db,
        user_id=user_id,
        action="DATA_DELETE_INITIATED",
        detail="User initiated irreversible data deletion.",
        ip=request.client.host if request.client else None,
    )

    # Anonymise / remove the user record
    current_user.email = f"deleted_{user_id}@deleted.invalid"
    if hasattr(current_user, "username"):
        current_user.username = f"deleted_{user_id}"
    if hasattr(current_user, "is_active"):
        current_user.is_active = False
    if hasattr(current_user, "deleted_at"):
        current_user.deleted_at = datetime.utcnow()

    db.commit()

    _log(
        db,
        user_id=user_id,
        action="DATA_DELETE_COMPLETED",
        detail="User personal data has been permanently deleted.",
        ip=request.client.host if request.client else None,
    )

    return {"detail": "Your personal data has been permanently deleted."}
