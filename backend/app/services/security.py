import json
import math
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import LoginEvent, User

# Thresholds
IMPOSSIBLE_TRAVEL_SPEED_KMH = 900  # max realistic travel speed
MAX_FAILED_ATTEMPTS = 5
FAILED_ATTEMPTS_WINDOW_MINUTES = 15
NEW_DEVICE_SCORE = 30.0
NEW_LOCATION_SCORE = 25.0
IMPOSSIBLE_TRAVEL_SCORE = 50.0
FAILED_ATTEMPTS_SCORE = 40.0
ANOMALY_ALERT_THRESHOLD = 50.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _device_fingerprint(user_agent: Optional[str], ip_address: str) -> str:
    raw = f"{user_agent or ''}:{ip_address.rsplit('.', 1)[0]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_anomaly_score(
    db: Session,
    user_id: int,
    ip_address: str,
    user_agent: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    now: Optional[datetime] = None,
) -> tuple[float, list[str]]:
    """
    Compare the current login attempt against historical baseline.
    Returns (score, reasons).
    """
    now = now or datetime.utcnow()
    score = 0.0
    reasons: list[str] = []

    fingerprint = _device_fingerprint(user_agent, ip_address)

    history = (
        db.query(LoginEvent)
        .filter(LoginEvent.user_id == user_id, LoginEvent.success == True)
        .order_by(LoginEvent.timestamp.desc())
        .limit(50)
        .all()
    )

    # --- New device check ---
    known_fingerprints = {e.device_fingerprint for e in history if e.device_fingerprint}
    if known_fingerprints and fingerprint not in known_fingerprints:
        score += NEW_DEVICE_SCORE
        reasons.append("new_device")

    # --- New location / impossible travel check ---
    if latitude is not None and longitude is not None and history:
        last = next((e for e in history if e.latitude is not None and e.longitude is not None), None)
        if last:
            distance_km = _haversine_km(last.latitude, last.longitude, latitude, longitude)
            elapsed_hours = max((now - last.timestamp).total_seconds() / 3600, 1e-6)
            speed_kmh = distance_km / elapsed_hours

            if speed_kmh > IMPOSSIBLE_TRAVEL_SPEED_KMH:
                score += IMPOSSIBLE_TRAVEL_SCORE
                reasons.append("impossible_travel")
            elif distance_km > 500:
                score += NEW_LOCATION_SCORE
                reasons.append("new_location")

    # --- Multiple failed attempts check ---
    window_start = now - timedelta(minutes=FAILED_ATTEMPTS_WINDOW_MINUTES)
    failed_count = (
        db.query(LoginEvent)
        .filter(
            LoginEvent.user_id == user_id,
            LoginEvent.success == False,
            LoginEvent.timestamp >= window_start,
        )
        .count()
    )
    if failed_count >= MAX_FAILED_ATTEMPTS:
        score += FAILED_ATTEMPTS_SCORE
        reasons.append(f"failed_attempts:{failed_count}")

    return score, reasons


def record_login_event(
    db: Session,
    user_id: int,
    ip_address: str,
    user_agent: Optional[str],
    success: bool,
    country: Optional[str] = None,
    city: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    now: Optional[datetime] = None,
) -> LoginEvent:
    """Persist a login event and compute its anomaly score."""
    now = now or datetime.utcnow()
    fingerprint = _device_fingerprint(user_agent, ip_address)

    anomaly_score, reasons = compute_anomaly_score(
        db, user_id, ip_address, user_agent, latitude, longitude, now
    )
    flagged = anomaly_score >= ANOMALY_ALERT_THRESHOLD

    event = LoginEvent(
        user_id=user_id,
        timestamp=now,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=fingerprint,
        country=country,
        city=city,
        latitude=latitude,
        longitude=longitude,
        success=success,
        anomaly_score=anomaly_score,
        flagged=flagged,
        flag_reasons=json.dumps(reasons) if reasons else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def should_alert(event: LoginEvent) -> bool:
    return event.flagged


def get_alert_message(event: LoginEvent, user_email: str) -> str:
    reasons = json.loads(event.flag_reasons) if event.flag_reasons else []
    reason_text = ", ".join(r.replace("_", " ") for r in reasons)
    return (
        f"Suspicious login detected for {user_email}.\n"
        f"Time: {event.timestamp.isoformat()} UTC\n"
        f"IP: {event.ip_address}\n"
        f"Location: {event.city or 'unknown'}, {event.country or 'unknown'}\n"
        f"Reasons: {reason_text}\n"
        f"Anomaly score: {event.anomaly_score:.1f}\n"
        "If this was not you, please secure your account immediately."
    )
