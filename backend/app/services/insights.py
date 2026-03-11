from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any


def get_week_range(reference_date: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the start (Monday) and end (Sunday) of the week for a given date."""
    if reference_date is None:
        reference_date = datetime.utcnow()
    start = reference_date - timedelta(days=reference_date.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start, end


def aggregate_expenses_by_category(expenses: list[dict]) -> dict[str, float]:
    """Sum expense amounts grouped by category."""
    totals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        category = expense.get("category", "Uncategorized")
        totals[category] += float(expense.get("amount", 0))
    return dict(totals)


def compute_trend(
    current_total: float, previous_total: float
) -> dict[str, Any]:
    """Compute percentage change and direction between two periods."""
    if previous_total == 0:
        change_pct = None
        direction = "neutral"
    else:
        change_pct = round((current_total - previous_total) / previous_total * 100, 2)
        direction = "up" if change_pct > 0 else ("down" if change_pct < 0 else "neutral")
    return {"change_pct": change_pct, "direction": direction}


def generate_recommendations(
    current_breakdown: dict[str, float],
    previous_breakdown: dict[str, float],
    top_n: int = 3,
) -> list[str]:
    """Generate actionable recommendations based on category spending changes."""
    recommendations: list[str] = []
    for category, amount in sorted(
        current_breakdown.items(), key=lambda x: x[1], reverse=True
    )[:top_n]:
        prev_amount = previous_breakdown.get(category, 0.0)
        if prev_amount == 0:
            recommendations.append(
                f"New spending detected in '{category}': ${amount:.2f}. "
                "Consider whether this is a recurring cost."
            )
        elif amount > prev_amount * 1.2:
            pct = round((amount - prev_amount) / prev_amount * 100)
            recommendations.append(
                f"'{category}' spending increased by {pct}% "
                f"(${prev_amount:.2f} → ${amount:.2f}). Review for savings opportunities."
            )
    if not recommendations:
        recommendations.append(
            "Spending is stable compared to last week. Keep up the good work!"
        )
    return recommendations


def build_weekly_digest(
    current_expenses: list[dict],
    previous_expenses: list[dict],
    week_start: datetime,
    week_end: datetime,
) -> dict[str, Any]:
    """Build the full weekly financial digest payload."""
    current_breakdown = aggregate_expenses_by_category(current_expenses)
    previous_breakdown = aggregate_expenses_by_category(previous_expenses)

    current_total = sum(current_breakdown.values())
    previous_total = sum(previous_breakdown.values())

    trend = compute_trend(current_total, previous_total)
    recommendations = generate_recommendations(current_breakdown, previous_breakdown)

    return {
        "week_start": week_start.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "total_spent": round(current_total, 2),
        "previous_total_spent": round(previous_total, 2),
        "trend": trend,
        "category_breakdown": {
            k: round(v, 2) for k, v in current_breakdown.items()
        },
        "previous_category_breakdown": {
            k: round(v, 2) for k, v in previous_breakdown.items()
        },
        "recommendations": recommendations,
    }
