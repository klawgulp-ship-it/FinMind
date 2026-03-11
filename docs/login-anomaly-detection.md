# Login Anomaly Detection

This document describes the suspicious-login detection system.

## Overview

Every login attempt (successful or not) is recorded in the `login_events` table.
After recording, an anomaly score is computed by comparing the current attempt
against the user's historical baseline. When the score exceeds the alert
threshold an alert is dispatched to the user via email and/or SMS.

## Database Schema

```sql
login_events
├── id                INTEGER  PRIMARY KEY
├── user_id           INTEGER  FK → users.id
├── timestamp         DATETIME NOT NULL
├── ip_address        VARCHAR  NOT NULL
├── user_agent        TEXT
├── device_fingerprint VARCHAR          -- sha256( user_agent + /24 subnet )
├── country           VARCHAR
├── city              VARCHAR
├── latitude          FLOAT
├── longitude         FLOAT
├── success           BOOLEAN  NOT NULL
├── anomaly_score     FLOAT    DEFAULT 0
├── flagged           BOOLEAN  DEFAULT false
└── flag_reasons      TEXT             -- JSON array of reason strings
```

## Anomaly Scoring

| Signal | Score added | Reason key |
|---|---|---|
| Device fingerprint not seen before | +30 | `new_device` |
| Distance > 500 km from last login | +25 | `new_location` |
| Impossible travel (speed > 900 km/h) | +50 | `impossible_travel` |
| ≥ 5 failed attempts in 15 minutes | +40 | `failed_attempts:<n>` |

Scores are **additive**. An event is **flagged** when the total score ≥ **50**.

## Alert Flow

1. `POST /auth/login` is called.
2. `record_login_event()` persists the event and calls `compute_anomaly_score()`.
3. If `should_alert(event)` returns `True`, `_send_alert()` is invoked.
4. `_send_alert()` currently logs the alert; wire in SendGrid / Twilio for production.

## Configuration

Adjust thresholds in `app/services/security.py`:

```python
IMPOSSIBLE_TRAVEL_SPEED_KMH = 900
MAX_FAILED_ATTEMPTS        = 5
FAILED_ATTEMPTS_WINDOW_MINUTES = 15
ANOMALY_ALERT_THRESHOLD    = 50.0
```

## Running Tests

```bash
pytest backend/tests/test_security.py -v
```

## Extending

- **Email alerts**: replace the `TODO` in `_send_alert()` with a SendGrid / SES call.
- **SMS alerts**: add a Twilio call using `user.phone`.
- **Geo-IP resolution**: populate `country`, `city`, `latitude`, `longitude` server-side
  using a library such as `geoip2` before calling `record_login_event()`.
- **Rate limiting**: combine the `failed_attempts` signal with a Redis-based
  sliding-window counter for real-time blocking.
