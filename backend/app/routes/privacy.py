import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _log(db: Session, user_id: int, action: str, detail: str = None, performed_by: int = None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        detail=detail,
        performed_by=performed_by,
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


@router.get("/export")
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and return a ZIP package containing the user's personal data as JSON.
    """
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": getattr(current_user, "username", None),
        "created_at": str(getattr(current_user, "created_at", "")),
        "updated_at": str(getattr(current_user, "updated_at", "")),
    }

    json_bytes = json.dumps(user_data, indent=2, default=str).encode("utf-8")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("user_data.json", json_bytes)
    zip_buffer.seek(0)

    _log(
        db,
        user_id=current_user.id,
        action="PII_EXPORT",
        detail="User requested personal data export.",
        performed_by=current_user.id,
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=user_{current_user.id}_data.zip"},
    )


@router.delete("/delete", status_code=status.HTTP_200_OK)
def delete_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Irreversibly delete the authenticated user's account and all associated data.
    An audit log entry is written before deletion.
    """
    user_id = current_user.id

    _log(
        db,
        user_id=user_id,
        action="PII_DELETE",
        detail="User requested irreversible account and data deletion.",
        performed_by=user_id,
    )

    db.delete(current_user)
    db.commit()

    return {"detail": "Your account and all associated data have been permanently deleted."}
