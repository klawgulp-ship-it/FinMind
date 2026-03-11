from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Expense


def get_weekly_summary(db: Session, user_id: str, end_date: Optional[datetime] = None):
    """Aggregate expense data over the past 7 days and compute trends/insights."""
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    prev_start_date = start_date - timedelta(days=7)

    current_expenses = (
        db.query(Expense)
        .filter(
            Expense.user_id == user_id,
            Expense.date >= start_date,
            Expense.date < end_date,
        )
        .all()
    )

    previous_expenses = (
        db.query(Expense)
        .filter(
            Expense.user_id == user_id,
            Expense.date >= prev_start_date,
            Expense.date < start_date,
        )
        .all()
    )

    current_total = sum(e.amount for e in current_expenses)
    previous_total = sum(e.amount for e in previous_expenses)

    if previous_total > 0:
        week_over_week_change_pct = ((current_total - previous_total) / previous_total) * 100
    else:
        week_over_week_change_pct = 0.0

    # Top categories
    category_totals = defaultdict(float)
    for expense in current_expenses:
        category_totals[expense.category_id] += expense.amount
    top_categories = sorted(
        [{"category_id": cat, "amount": amt} for cat, amt in category_totals.items()],
        key=lambda x: x["amount"],
        reverse=True,
    )

    # Previous week category totals for anomaly detection
    prev_category_totals = defaultdict(float)
    for expense in previous_expenses:
        prev_category_totals[expense.category_id] += expense.amount

    # Anomalies: categories where spending increased by more than 50%
    anomalies = []
    for cat, amt in category_totals.items():
        prev_amt = prev_category_totals.get(cat, 0)
        if prev_amt > 0 and ((amt - prev_amt) / prev_amt) > 0.5:
            anomalies.append(
                {
                    "category_id": cat,
                    "current_amount": amt,
                    "previous_amount": prev_amt,
                    "change_pct": ((amt - prev_amt) / prev_amt) * 100,
                }
            )
        elif prev_amt == 0 and amt > 0:
            anomalies.append(
                {
                    "category_id": cat,
                    "current_amount": amt,
                    "previous_amount": 0,
                    "change_pct": 100.0,
                }
            )

    # Daily breakdown
    daily_totals = defaultdict(float)
    for expense in current_expenses:
        day_key = expense.date.strftime("%Y-%m-%d")
        daily_totals[day_key] += expense.amount

    tips = []
    if week_over_week_change_pct > 20:
        tips.append("Your spending increased significantly compared to last week. Consider reviewing discretionary expenses.")
    elif week_over_week_change_pct < -20:
        tips.append("Great job! Your spending decreased compared to last week.")
    if top_categories:
        tips.append(f"Your highest spending category this week was '{top_categories[0]['category_id']}'.")

    return {
        "period_start": start_date.strftime("%Y-%m-%d"),
        "period_end": end_date.strftime("%Y-%m-%d"),
        "current_week_total": current_total,
        "previous_week_total": previous_total,
        "week_over_week_change_pct": round(week_over_week_change_pct, 2),
        "top_categories": top_categories[:5],
        "anomalies": anomalies,
        "daily_breakdown": dict(sorted(daily_totals.items())),
        "tips": tips,
    }
