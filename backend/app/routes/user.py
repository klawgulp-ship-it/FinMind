import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.session import get_db
from app.models.audit_log import ACTION_DELETE, ACTION_EXPORT, AuditLogEntry

router = APIRouter(prefix="/users", tags=["users"])


class DeleteConfirmRequest(BaseModel):
    confirm: bool


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _write_audit_log(db, entry: AuditLogEntry) -> None:
    await db.execute(
        """
        INSERT INTO audit_log (user_id, action, performed_by, ip_address, user_agent, metadata, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        entry.user_id,
        entry.action,
        entry.performed_by,
        entry.ip_address,
        entry.user_agent,
        json.dumps(entry.metadata) if entry.metadata else None,
        datetime.utcnow(),
    )


async def _fetch_user(db, user_id: int) -> dict:
    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return dict(row)


@router.get("/{user_id}/export")
async def export_user_data(user_id: int, request: Request, db=Depends(get_db)):
    """
    Export all personal data for a user as a JSON package.
    Logs the export action to the audit trail.
    """
    user = await _fetch_user(db, user_id)

    audit_logs = await db.fetch(
        "SELECT id, action, performed_by, ip_address, created_at FROM audit_log WHERE user_id = $1 ORDER BY created_at DESC",
        user_id,
    )

    export_package = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
        },
        "audit_history": [
            {
                "id": row["id"],
                "action": row["action"],
                "performed_by": row["performed_by"],
                "ip_address": row["ip_address"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in audit_logs
        ],
    }

    await _write_audit_log(
        db,
        AuditLogEntry(
            user_id=user_id,
            action=ACTION_EXPORT,
            performed_by=user_id,
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata={"exported_fields": ["user", "audit_history"]},
        ),
    )

    return JSONResponse(content=export_package, status_code=status.HTTP_200_OK)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_data(user_id: int, body: DeleteConfirmRequest, request: Request, db=Depends(get_db)):
    """
    Irreversibly delete all personal data for a user.
    Requires explicit confirmation. Logs deletion to audit trail before removal.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion must be explicitly confirmed with confirm=true",
        )

    user = await _fetch_user(db, user_id)

    await _write_audit_log(
        db,
        AuditLogEntry(
            user_id=user_id,
            action=ACTION_DELETE,
            performed_by=user_id,
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata={
                "deleted_email": user["email"],
                "deleted_name": user["name"],
            },
        ),
    )

    async with db.transaction():
        await db.execute("DELETE FROM users WHERE id = $1", user_id)

    return {"detail": "User data permanently deleted", "user_id": user_id}
