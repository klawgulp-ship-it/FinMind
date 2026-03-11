from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

from app.services.insights import build_weekly_digest, get_week_range

insights_bp = Blueprint("insights", __name__, url_prefix="/api/insights")


def _get_expenses_for_range(
    start: datetime, end: datetime
) -> list[dict]:
    """
    Fetch expenses for a given date range.

    Replace this stub with your actual database query, e.g.:
        Expense.query.filter(
            Expense.date >= start, Expense.date <= end
        ).all()
    and convert ORM objects to dicts.
    """
    # Stub: return an empty list until wired to real data layer.
    return []


@insights_bp.route("/weekly", methods=["GET"])
def weekly_digest():
    """
    GET /api/insights/weekly

    Query params:
        date (str, optional): ISO date string (YYYY-MM-DD) for any day within
                              the desired week. Defaults to current UTC week.

    Returns a JSON payload with:
        - week_start / week_end
        - total_spent & previous_total_spent
        - trend (change_pct, direction)
        - category_breakdown & previous_category_breakdown
        - recommendations (list of actionable strings)
    """
    date_param = request.args.get("date")
    if date_param:
        try:
            reference_date = datetime.fromisoformat(date_param)
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        reference_date = datetime.utcnow()

    week_start, week_end = get_week_range(reference_date)
    prev_week_start = week_start - timedelta(weeks=1)
    prev_week_end = week_end - timedelta(weeks=1)

    current_expenses = _get_expenses_for_range(week_start, week_end)
    previous_expenses = _get_expenses_for_range(prev_week_start, prev_week_end)

    digest = build_weekly_digest(
        current_expenses, previous_expenses, week_start, week_end
    )
    return jsonify(digest), 200
