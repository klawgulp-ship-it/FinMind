import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.security import record_login_event, should_alert, get_alert_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    # Optional geo metadata supplied by client or resolved server-side
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    anomaly_detected: bool = False


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _fake_verify_password(plain: str, hashed: str) -> bool:
    """Placeholder — replace with passlib or equivalent."""
    import hashlib
    return hashlib.sha256(plain.encode()).hexdigest() == hashed


def _create_access_token(user_id: int) -> str:
    """Placeholder — replace with python-jose JWT creation."""
    import base64, json
    payload = json.dumps({"sub": user_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _send_alert(user: User, message: str) -> None:
    """Dispatch alert via email and/or SMS. Extend with real providers."""
    logger.warning("SECURITY ALERT for user %s: %s", user.email, message)
    # TODO: integrate email provider (e.g. SendGrid) and SMS provider (e.g. Twilio)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    success = bool(
        user
        and user.is_active
        and _fake_verify_password(payload.password, user.hashed_password)
    )

    event = record_login_event(
        db=db,
        user_id=user.id if user else 0,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
        country=payload.country,
        city=payload.city,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    anomaly_detected = should_alert(event)
    if anomaly_detected and user:
        message = get_alert_message(event, user.email)
        _send_alert(user, message)

    token = _create_access_token(user.id)
    return LoginResponse(access_token=token, anomaly_detected=anomaly_detected)
