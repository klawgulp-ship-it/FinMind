from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.services import audit_logger, pii_service

router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_user_id(request: Request) -> int:
    """
    Stub: replace with your real auth dependency (JWT decode, session, etc.).
    Raises 401 if not authenticated.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return int(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id")


@router.get("/me/export")
def export_my_data(
    format: str = "json",
    request: Request = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Export the authenticated user's personal data as JSON or CSV.
    """
    audit_logger.log_event(
        db=db,
        event_type=audit_logger.EVENT_DATA_EXPORT,
        user_id=current_user_id,
        actor_id=current_user_id,
        description="User requested data export",
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        extra={"format": format},
    )

    if format.lower() == "csv":
        csv_data = pii_service.export_as_csv(db, current_user_id)
        if csv_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="my_data_{current_user_id}.csv"'},
        )

    json_data = pii_service.export_as_json(db, current_user_id)
    if json_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="my_data_{current_user_id}.json"'},
    )


@router.delete("/me", status_code=status.HTTP_200_OK)
def delete_my_account(
    request: Request = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Irreversibly delete the authenticated user's account and scrub all PII.
    This action cannot be undone.
    """
    deleted = pii_service.irreversibly_delete_user(
        db=db,
        user_id=current_user_id,
        actor_id=current_user_id,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already deleted")

    return {"detail": "Your account and personal data have been permanently deleted."}


@router.get("/admin/users/{user_id}/export")
def admin_export_user_data(
    user_id: int,
    format: str = "json",
    request: Request = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Admin: export any user's personal data as JSON or CSV.
    Requires admin privilege check (add your own RBAC guard here).
    """
    audit_logger.log_event(
        db=db,
        event_type=audit_logger.EVENT_DATA_EXPORT,
        user_id=user_id,
        actor_id=current_user_id,
        description=f"Admin requested data export for user {user_id}",
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        extra={"format": format, "requested_by": current_user_id},
    )

    if format.lower() == "csv":
        csv_data = pii_service.export_as_csv(db, user_id)
        if csv_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="user_data_{user_id}.csv"'},
        )

    json_data = pii_service.export_as_json(db, user_id)
    if json_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="user_data_{user_id}.json"'},
    )


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_200_OK)
def admin_delete_user(
    user_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Admin: irreversibly delete any user's account and scrub all PII.
    Requires admin privilege check (add your own RBAC guard here).
    """
    deleted = pii_service.irreversibly_delete_user(
        db=db,
        user_id=user_id,
        actor_id=current_user_id,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already deleted")

    return {"detail": f"User {user_id} and all associated personal data have been permanently deleted."}
