from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.services.insights import get_weekly_summary

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/weekly-summary")
def weekly_summary(
    end_date: Optional[str] = Query(None, description="ISO date string for the end of the 7-day window (defaults to today)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a weekly financial summary for the authenticated user."""
    parsed_end_date = None
    if end_date:
        parsed_end_date = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    return get_weekly_summary(db=db, user_id=current_user.id, end_date=parsed_end_date)
