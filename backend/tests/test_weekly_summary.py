from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.insights import get_weekly_summary


def _make_expense(amount: float, category_id: str, date: datetime):
    e = MagicMock()
    e.amount = amount
    e.category_id = category_id
    e.date = date
    return e


def _make_db(current_expenses, previous_expenses):
    """Return a mock db whose query chain returns the given expense lists."""
    db = MagicMock()
    call_count = {"n": 0}

    def fake_all():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return current_expenses
        return previous_expenses

    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.all.side_effect = fake_all
    db.query.return_value = query_mock
    return db


def test_weekly_summary_basic():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [
        _make_expense(100.0, "food", now - timedelta(days=1)),
        _make_expense(50.0, "transport", now - timedelta(days=2)),
    ]
    previous = [
        _make_expense(80.0, "food", now - timedelta(days=8)),
    ]
    db = _make_db(current, previous)
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert result["current_week_total"] == 150.0
    assert result["previous_week_total"] == 80.0
    assert result["week_over_week_change_pct"] == pytest.approx(87.5, 0.01)
    assert len(result["top_categories"]) == 2
    assert result["top_categories"][0]["category_id"] == "food"
    assert result["top_categories"][0]["amount"] == 100.0
    assert result["period_start"] == "2024-06-03"
    assert result["period_end"] == "2024-06-10"


def test_weekly_summary_no_previous():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [_make_expense(200.0, "food", now - timedelta(days=1))]
    db = _make_db(current, [])
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert result["previous_week_total"] == 0.0
    assert result["week_over_week_change_pct"] == 0.0


def test_weekly_summary_anomaly_detected():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [_make_expense(300.0, "food", now - timedelta(days=1))]
    previous = [_make_expense(100.0, "food", now - timedelta(days=8))]
    db = _make_db(current, previous)
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["category_id"] == "food"
    assert result["anomalies"][0]["change_pct"] == pytest.approx(200.0, 0.01)


def test_weekly_summary_no_anomaly_small_change():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [_make_expense(110.0, "food", now - timedelta(days=1))]
    previous = [_make_expense(100.0, "food", now - timedelta(days=8))]
    db = _make_db(current, previous)
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert result["anomalies"] == []


def test_weekly_summary_tips_increase():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [_make_expense(500.0, "food", now - timedelta(days=1))]
    previous = [_make_expense(100.0, "food", now - timedelta(days=8))]
    db = _make_db(current, previous)
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert any("increased" in tip for tip in result["tips"])


def test_weekly_summary_tips_decrease():
    now = datetime(2024, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    current = [_make_expense(50.0, "food", now - timedelta(days=1))]
    previous = [_make_expense(500.0, "food", now - timedelta(days=8))]
    db = _make_db(current, previous)
    result = get_weekly_summary(db=db, user_id="user1", end_date=now)

    assert any("decreased" in tip for tip in result["tips"])
