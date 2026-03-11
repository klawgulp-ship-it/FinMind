import pytest
from datetime import datetime

from app.services.insights import (
    aggregate_expenses_by_category,
    build_weekly_digest,
    compute_trend,
    generate_recommendations,
    get_week_range,
)


# ---------------------------------------------------------------------------
# get_week_range
# ---------------------------------------------------------------------------

class TestGetWeekRange:
    def test_returns_monday_as_start(self):
        wednesday = datetime(2024, 3, 13)  # Wednesday
        start, _ = get_week_range(wednesday)
        assert start.weekday() == 0  # Monday

    def test_returns_sunday_as_end(self):
        wednesday = datetime(2024, 3, 13)
        _, end = get_week_range(wednesday)
        assert end.weekday() == 6  # Sunday

    def test_start_at_midnight(self):
        start, _ = get_week_range(datetime(2024, 3, 13))
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0

    def test_end_at_end_of_day(self):
        _, end = get_week_range(datetime(2024, 3, 13))
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59

    def test_defaults_to_current_week(self):
        start, end = get_week_range()
        now = datetime.utcnow()
        assert start <= now <= end

    def test_span_is_seven_days(self):
        start, end = get_week_range(datetime(2024, 3, 13))
        delta = end - start
        assert delta.days == 6


# ---------------------------------------------------------------------------
# aggregate_expenses_by_category
# ---------------------------------------------------------------------------

class TestAggregateExpensesByCategory:
    def test_sums_same_category(self):
        expenses = [
            {"category": "Food", "amount": 10.0},
            {"category": "Food", "amount": 5.0},
        ]
        result = aggregate_expenses_by_category(expenses)
        assert result["Food"] == 15.0

    def test_groups_multiple_categories(self):
        expenses = [
            {"category": "Food", "amount": 10.0},
            {"category": "Transport", "amount": 20.0},
        ]
        result = aggregate_expenses_by_category(expenses)
        assert result["Food"] == 10.0
        assert result["Transport"] == 20.0

    def test_empty_list_returns_empty_dict(self):
        assert aggregate_expenses_by_category([]) == {}

    def test_missing_category_defaults_to_uncategorized(self):
        expenses = [{"amount": 50.0}]
        result = aggregate_expenses_by_category(expenses)
        assert "Uncategorized" in result
        assert result["Uncategorized"] == 50.0

    def test_missing_amount_treated_as_zero(self):
        expenses = [{"category": "Food"}]
        result = aggregate_expenses_by_category(expenses)
        assert result["Food"] == 0.0


# ---------------------------------------------------------------------------
# compute_trend
# ---------------------------------------------------------------------------

class TestComputeTrend:
    def test_increase(self):
        result = compute_trend(120.0, 100.0)
        assert result["direction"] == "up"
        assert result["change_pct"] == 20.0

    def test_decrease(self):
        result = compute_trend(80.0, 100.0)
        assert result["direction"] == "down"
        assert result["change_pct"] == -20.0

    def test_no_change(self):
        result = compute_trend(100.0, 100.0)
        assert result["direction"] == "neutral"
        assert result["change_pct"] == 0.0

    def test_previous_zero_returns_none_change(self):
        result = compute_trend(50.0, 0.0)
        assert result["change_pct"] is None
        assert result["direction"] == "neutral"

    def test_rounding(self):
        result = compute_trend(133.33, 100.0)
        assert result["change_pct"] == 33.33


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    def test_new_category_recommendation(self):
        recs = generate_recommendations({"Dining": 50.0}, {})
        assert any("New spending" in r for r in recs)

    def test_spike_recommendation(self):
        recs = generate_recommendations(
            {"Dining": 200.0}, {"Dining": 100.0}
        )
        assert any("Dining" in r and "increased" in r for r in recs)

    def test_stable_spending_positive_message(self):
        recs = generate_recommendations(
            {"Dining": 100.0}, {"Dining": 100.0}
        )
        assert any("stable" in r.lower() for r in recs)

    def test_limits_to_top_n(self):
        current = {f"Cat{i}": float(i * 10) for i in range(1, 11)}
        recs = generate_recommendations(current, {}, top_n=3)
        # Should only analyse top 3 categories; 7 new-spending + stable check not triggered
        assert len(recs) <= 3

    def test_empty_current_returns_stable(self):
        recs = generate_recommendations({}, {})
        assert any("stable" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# build_weekly_digest
# ---------------------------------------------------------------------------

class TestBuildWeeklyDigest:
    def _make_expenses(self, entries):
        return [{"category": cat, "amount": amt} for cat, amt in entries]

    def setup_method(self):
        self.week_start = datetime(2024, 3, 11)
        self.week_end = datetime(2024, 3, 17)
        self.current = self._make_expenses([("Food", 80.0), ("Transport", 40.0)])
        self.previous = self._make_expenses([("Food", 60.0), ("Transport", 40.0)])

    def test_returns_correct_keys(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        expected_keys = {
            "week_start", "week_end", "total_spent", "previous_total_spent",
            "trend", "category_breakdown", "previous_category_breakdown",
            "recommendations",
        }
        assert expected_keys == set(digest.keys())

    def test_total_spent(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert digest["total_spent"] == 120.0

    def test_previous_total_spent(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert digest["previous_total_spent"] == 100.0

    def test_trend_direction_up(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert digest["trend"]["direction"] == "up"

    def test_week_dates_are_iso_strings(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert digest["week_start"] == "2024-03-11"
        assert digest["week_end"] == "2024-03-17"

    def test_category_breakdown_present(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert digest["category_breakdown"]["Food"] == 80.0
        assert digest["category_breakdown"]["Transport"] == 40.0

    def test_recommendations_is_list(self):
        digest = build_weekly_digest(
            self.current, self.previous, self.week_start, self.week_end
        )
        assert isinstance(digest["recommendations"], list)
        assert len(digest["recommendations"]) > 0

    def test_empty_expenses(self):
        digest = build_weekly_digest([], [], self.week_start, self.week_end)
        assert digest["total_spent"] == 0.0
        assert digest["previous_total_spent"] == 0.0
        assert digest["category_breakdown"] == {}


# ---------------------------------------------------------------------------
# Route integration (light)
# ---------------------------------------------------------------------------

class TestWeeklyDigestRoute:
    @pytest.fixture()
    def client(self):
        """Create a minimal Flask test client."""
        from flask import Flask
        from app.routes.insights import insights_bp

        app = Flask(__name__)
        app.register_blueprint(insights_bp)
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_get_weekly_returns_200(self, client):
        response = client.get("/api/insights/weekly")
        assert response.status_code == 200

    def test_get_weekly_response_has_expected_keys(self, client):
        data = client.get("/api/insights/weekly").get_json()
        assert "week_start" in data
        assert "total_spent" in data
        assert "recommendations" in data

    def test_get_weekly_with_date_param(self, client):
        response = client.get("/api/insights/weekly?date=2024-03-13")
        assert response.status_code == 200
        data = response.get_json()
        assert data["week_start"] == "2024-03-11"
        assert data["week_end"] == "2024-03-17"

    def test_get_weekly_invalid_date_returns_400(self, client):
        response = client.get("/api/insights/weekly?date=not-a-date")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
