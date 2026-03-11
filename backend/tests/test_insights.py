"""Tests for the weekly financial digest service and API endpoints."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.insights import (
    _aggregate,
    _calculate_trends,
    _generate_insights,
    get_week_bounds,
)


# ---------------------------------------------------------------------------
# Unit tests — pure helpers (no DB)
# ---------------------------------------------------------------------------

class TestGetWeekBounds:
    def test_monday_input(self):
        monday = date(2024, 1, 1)  # known Monday
        start, end = get_week_bounds(monday)
        assert start == monday
        assert end == date(2024, 1, 7)

    def test_wednesday_input(self):
        wednesday = date(2024, 1, 3)
        start, end = get_week_bounds(wednesday)
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 7)

    def test_sunday_input(self):
        sunday = date(2024, 1, 7)
        start, end = get_week_bounds(sunday)
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 7)

    def test_defaults_to_today(self):
        start, end = get_week_bounds()
        today = date.today()
        assert start <= today <= end
        assert (end - start).days == 6


class TestAggregate:
    def test_empty(self):
        total, breakdown = _aggregate([])
        assert total == 0.0
        assert breakdown == {}

    def test_single_expense(self):
        expenses = [{"amount": "50.00", "category": "Food", "description": "", "date": date.today()}]
        total, breakdown = _aggregate(expenses)
        assert total == 50.0
        assert breakdown == {"Food": 50.0}

    def test_multiple_categories(self):
        expenses = [
            {"amount": "30.00", "category": "Food", "description": "", "date": date.today()},
            {"amount": "20.00", "category": "Food", "description": "", "date": date.today()},
            {"amount": "100.00", "category": "Rent", "description": "", "date": date.today()},
        ]
        total, breakdown = _aggregate(expenses)
        assert total == 150.0
        assert breakdown["Food"] == 50.0
        assert breakdown["Rent"] == 100.0


class TestCalculateTrends:
    def test_no_previous_data(self):
        trends = _calculate_trends(100.0, {"Food": 100.0}, 0.0)
        assert trends["week_over_week_change_pct"] is None
        assert trends["top_category"] == "Food"

    def test_increase(self):
        trends = _calculate_trends(120.0, {"Food": 120.0}, 100.0)
        assert trends["week_over_week_change_pct"] == 20.0

    def test_decrease(self):
        trends = _calculate_trends(80.0, {"Food": 80.0}, 100.0)
        assert trends["week_over_week_change_pct"] == -20.0

    def test_no_change(self):
        trends = _calculate_trends(100.0, {"Food": 100.0}, 100.0)
        assert trends["week_over_week_change_pct"] == 0.0

    def test_top_category_selected(self):
        by_cat = {"Food": 40.0, "Rent": 200.0, "Entertainment": 60.0}
        trends = _calculate_trends(300.0, by_cat, 0.0)
        assert trends["top_category"] == "Rent"
        assert trends["top_category_amount"] == 200.0

    def test_empty_categories(self):
        trends = _calculate_trends(0.0, {}, 0.0)
        assert trends["top_category"] is None


class TestGenerateInsights:
    def _trends(self, change_pct, top_cat="Food", top_amt=50.0, prev=100.0):
        return {
            "week_over_week_change_pct": change_pct,
            "top_category": top_cat,
            "top_category_amount": top_amt,
            "previous_week_total": prev,
        }

    def test_includes_total(self):
        text = _generate_insights(150.0, {"Food": 150.0}, self._trends(50.0))
        assert "$150.00" in text

    def test_increase_message(self):
        text = _generate_insights(150.0, {"Food": 150.0}, self._trends(50.0))
        assert "increased" in text.lower()

    def test_decrease_message(self):
        text = _generate_insights(80.0, {"Food": 80.0}, self._trends(-20.0))
        assert "decreased" in text.lower()

    def test_no_previous_message(self):
        text = _generate_insights(80.0, {"Food": 80.0}, self._trends(None))
        assert "no data" in text.lower()

    def test_top_category_mentioned(self):
        text = _generate_insights(100.0, {"Rent": 100.0}, self._trends(0.0, top_cat="Rent", top_amt=100.0))
        assert "Rent" in text


# ---------------------------------------------------------------------------
# Integration-style tests — API endpoints (Flask test client)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create a minimal Flask app with the insights blueprint registered."""
    from flask import Flask
    from app.routes.insights import bp

    flask_app = Flask(__name__)
    flask_app.register_blueprint(bp)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


_SAMPLE_DIGEST = {
    "id": 1,
    "user_id": 42,
    "week_start": "2024-01-01",
    "week_end": "2024-01-07",
    "total_spent": 250.0,
    "category_breakdown": {"Food": 150.0, "Transport": 100.0},
    "trends": {"week_over_week_change_pct": 10.0, "top_category": "Food",
               "top_category_amount": 150.0, "previous_week_total": 227.27},
    "insights": "Total spending this week: $250.00.",
    "created_at": "2024-01-08T00:00:00",
}


class TestWeeklyDigestEndpoint:
    def test_missing_user_id(self, client):
        resp = client.post("/api/insights/weekly-digest", json={})
        assert resp.status_code == 400
        assert "user_id" in resp.get_json()["error"]

    def test_invalid_ref_date(self, client):
        resp = client.post("/api/insights/weekly-digest", json={"user_id": 1, "ref_date": "not-a-date"})
        assert resp.status_code == 400

    @patch("app.routes.insights.generate_weekly_digest", return_value=_SAMPLE_DIGEST)
    def test_success(self, mock_gen, client):
        resp = client.post("/api/insights/weekly-digest", json={"user_id": 42})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user_id"] == 42
        assert data["total_spent"] == 250.0
        mock_gen.assert_called_once_with(42, None)

    @patch("app.routes.insights.generate_weekly_digest", return_value=_SAMPLE_DIGEST)
    def test_success_with_ref_date(self, mock_gen, client):
        resp = client.post(
            "/api/insights/weekly-digest",
            json={"user_id": 42, "ref_date": "2024-01-03"},
        )
        assert resp.status_code == 200
        mock_gen.assert_called_once_with(42, date(2024, 1, 3))


class TestWeeklyDigestHistoryEndpoint:
    def test_missing_user_id(self, client):
        resp = client.get("/api/insights/weekly-digest/history")
        assert resp.status_code == 400

    def test_invalid_limit(self, client):
        resp = client.get("/api/insights/weekly-digest/history?user_id=1&limit=abc")
        assert resp.status_code == 400

    def test_negative_limit(self, client):
        resp = client.get("/api/insights/weekly-digest/history?user_id=1&limit=-1")
        assert resp.status_code == 400

    @patch("app.routes.insights.get_digest_history", return_value=[_SAMPLE_DIGEST])
    def test_success(self, mock_hist, client):
        resp = client.get("/api/insights/weekly-digest/history?user_id=42")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert data[0]["user_id"] == 42
        mock_hist.assert_called_once_with(42, 10)

    @patch("app.routes.insights.get_digest_history", return_value=[])
    def test_success_empty(self, mock_hist, client):
        resp = client.get("/api/insights/weekly-digest/history?user_id=99&limit=5")
        assert resp.status_code == 200
        assert resp.get_json() == []
        mock_hist.assert_called_once_with(99, 5)
