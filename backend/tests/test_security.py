import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from app.services.security import (
    _haversine_km,
    _device_fingerprint,
    compute_anomaly_score,
    record_login_event,
    should_alert,
    get_alert_message,
    ANOMALY_ALERT_THRESHOLD,
)
from app.models.user import LoginEvent


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point(self):
        assert _haversine_km(0, 0, 0, 0) == pytest.approx(0.0)

    def test_known_distance(self):
        # London -> Paris ≈ 340 km
        km = _haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330 < km < 360


class TestDeviceFingerprint:
    def test_deterministic(self):
        fp1 = _device_fingerprint("Mozilla/5.0", "1.2.3.4")
        fp2 = _device_fingerprint("Mozilla/5.0", "1.2.3.4")
        assert fp1 == fp2

    def test_different_agents_differ(self):
        fp1 = _device_fingerprint("Mozilla/5.0", "1.2.3.4")
        fp2 = _device_fingerprint("curl/7.0", "1.2.3.4")
        assert fp1 != fp2

    def test_same_subnet_same_fingerprint(self):
        # last octet differs → same /24 subnet → same fingerprint
        fp1 = _device_fingerprint("Mozilla/5.0", "1.2.3.1")
        fp2 = _device_fingerprint("Mozilla/5.0", "1.2.3.99")
        assert fp1 == fp2


# ---------------------------------------------------------------------------
# Integration-style tests using a mock DB session
# ---------------------------------------------------------------------------

def _make_event(
    user_id=1,
    ip="1.2.3.4",
    user_agent="Mozilla/5.0",
    success=True,
    lat=40.7128,
    lon=-74.0060,
    ts=None,
    fingerprint=None,
):
    e = MagicMock(spec=LoginEvent)
    e.user_id = user_id
    e.ip_address = ip
    e.user_agent = user_agent
    e.success = success
    e.latitude = lat
    e.longitude = lon
    e.timestamp = ts or datetime.utcnow() - timedelta(hours=1)
    e.device_fingerprint = fingerprint or _device_fingerprint(user_agent, ip)
    return e


def _mock_db(history=None, failed_count=0):
    db = MagicMock()
    query_mock = MagicMock()
    db.query.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.count.return_value = failed_count
    query_mock.all.return_value = history or []
    return db


class TestComputeAnomalyScore:
    def test_no_history_zero_score(self):
        db = _mock_db(history=[])
        score, reasons = compute_anomaly_score(db, 1, "1.2.3.4", "UA", None, None)
        assert score == 0.0
        assert reasons == []

    def test_new_device_flagged(self):
        existing = _make_event(fingerprint="aabbccdd11223344")
        db = _mock_db(history=[existing])
        score, reasons = compute_anomaly_score(db, 1, "9.9.9.9", "DifferentBrowser", None, None)
        assert "new_device" in reasons
        assert score >= 30.0

    def test_impossible_travel_flagged(self):
        # Last login in New York, now logging in from Sydney — 1 minute later
        last = _make_event(lat=-33.8688, lon=151.2093, ts=datetime.utcnow() - timedelta(minutes=1))
        last.device_fingerprint = _device_fingerprint("Mozilla/5.0", "1.2.3.4")
        db = _mock_db(history=[last])
        now = datetime.utcnow()
        score, reasons = compute_anomaly_score(
            db, 1, "1.2.3.4", "Mozilla/5.0", 40.7128, -74.0060, now
        )
        assert "impossible_travel" in reasons
        assert score >= 50.0

    def test_new_location_score(self):
        # Last login NY; now login LA (≈3940 km apart, 2 h later → speed OK but distance > 500)
        last = _make_event(lat=40.7128, lon=-74.0060, ts=datetime.utcnow() - timedelta(hours=2))
        last.device_fingerprint = _device_fingerprint("Mozilla/5.0", "1.2.3.4")
        db = _mock_db(history=[last])
        now = datetime.utcnow()
        score, reasons = compute_anomaly_score(
            db, 1, "1.2.3.4", "Mozilla/5.0", 34.0522, -118.2437, now
        )
        # Speed ≈ 1970 km/h — above threshold, so impossible_travel wins
        assert len(reasons) > 0

    def test_failed_attempts_flagged(self):
        db = _mock_db(history=[], failed_count=6)
        score, reasons = compute_anomaly_score(db, 1, "1.2.3.4", "UA", None, None)
        assert any(r.startswith("failed_attempts") for r in reasons)
        assert score >= 40.0

    def test_known_device_no_new_device_reason(self):
        ip = "1.2.3.4"
        ua = "Mozilla/5.0"
        fp = _device_fingerprint(ua, ip)
        existing = _make_event(ip=ip, user_agent=ua, fingerprint=fp)
        db = _mock_db(history=[existing])
        score, reasons = compute_anomaly_score(db, 1, ip, ua, None, None)
        assert "new_device" not in reasons


class TestShouldAlert:
    def test_flagged_event_triggers_alert(self):
        event = MagicMock(spec=LoginEvent)
        event.flagged = True
        assert should_alert(event) is True

    def test_clean_event_no_alert(self):
        event = MagicMock(spec=LoginEvent)
        event.flagged = False
        assert should_alert(event) is False


class TestGetAlertMessage:
    def test_message_contains_key_fields(self):
        event = MagicMock(spec=LoginEvent)
        event.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        event.ip_address = "10.0.0.1"
        event.city = "Berlin"
        event.country = "DE"
        event.flag_reasons = json.dumps(["impossible_travel", "new_device"])
        event.anomaly_score = 80.0
        msg = get_alert_message(event, "user@example.com")
        assert "user@example.com" in msg
        assert "10.0.0.1" in msg
        assert "impossible travel" in msg
        assert "new device" in msg
        assert "80.0" in msg

    def test_message_no_reasons(self):
        event = MagicMock(spec=LoginEvent)
        event.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        event.ip_address = "10.0.0.1"
        event.city = None
        event.country = None
        event.flag_reasons = None
        event.anomaly_score = 55.0
        msg = get_alert_message(event, "user@example.com")
        assert "user@example.com" in msg


class TestRecordLoginEvent:
    def test_event_persisted_and_returned(self):
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = []
        query_mock.count.return_value = 0

        event = record_login_event(
            db=db,
            user_id=1,
            ip_address="1.2.3.4",
            user_agent="Mozilla/5.0",
            success=True,
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
