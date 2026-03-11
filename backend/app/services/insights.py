from datetime import date, timedelta
from typing import Any

from app.db.connection import get_db


def get_week_bounds(ref: date | None = None) -> tuple[date, date]:
    """Return the Monday and Sunday surrounding *ref* (defaults to today)."""
    ref = ref or date.today()
    week_start = ref - timedelta(days=ref.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _fetch_expenses(user_id: int, week_start: date, week_end: date) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT amount, category, description, date
                FROM expenses
                WHERE user_id = %s AND date BETWEEN %s AND %s
                ORDER BY date
                """,
                (user_id, week_start, week_end),
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _aggregate(expenses: list[dict]) -> tuple[float, dict[str, float]]:
    total = 0.0
    by_category: dict[str, float] = {}
    for exp in expenses:
        amt = float(exp["amount"])
        total += amt
        by_category[exp["category"]] = by_category.get(exp["category"], 0.0) + amt
    return total, by_category


def _fetch_previous_total(user_id: int, prev_start: date, prev_end: date) -> float:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE user_id = %s AND date BETWEEN %s AND %s
                """,
                (user_id, prev_start, prev_end),
            )
            row = cur.fetchone()
            return float(row[0]) if row else 0.0


def _calculate_trends(
    total: float,
    by_category: dict[str, float],
    prev_total: float,
) -> dict[str, Any]:
    if prev_total == 0:
        week_over_week_pct = None
    else:
        week_over_week_pct = round((total - prev_total) / prev_total * 100, 2)

    top_category = max(by_category, key=lambda k: by_category[k]) if by_category else None

    return {
        "week_over_week_change_pct": week_over_week_pct,
        "top_category": top_category,
        "top_category_amount": by_category.get(top_category, 0.0) if top_category else 0.0,
        "previous_week_total": prev_total,
    }


def _generate_insights(
    total: float,
    by_category: dict[str, float],
    trends: dict[str, Any],
) -> str:
    lines: list[str] = []

    lines.append(f"Total spending this week: ${total:.2f}.")

    change = trends["week_over_week_change_pct"]
    if change is None:
        lines.append("No data available for the previous week to compare.")
    elif change > 0:
        lines.append(f"Spending increased by {change}% compared to last week.")
    elif change < 0:
        lines.append(f"Spending decreased by {abs(change)}% compared to last week — great job!")
    else:
        lines.append("Spending is on par with last week.")

    if trends["top_category"]:
        lines.append(
            f"Highest spend category: {trends['top_category']} "
            f"(${trends['top_category_amount']:.2f})."
        )

    if by_category:
        sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        breakdown = ", ".join(f"{cat}: ${amt:.2f}" for cat, amt in sorted_cats)
        lines.append(f"Category breakdown — {breakdown}.")

    return " ".join(lines)


def _upsert_digest(
    user_id: int,
    week_start: date,
    week_end: date,
    total: float,
    by_category: dict[str, float],
    trends: dict[str, Any],
    insights: str,
) -> dict[str, Any]:
    import json

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO weekly_digest
                    (user_id, week_start, week_end, total_spent,
                     category_breakdown, trends, insights)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, week_start) DO UPDATE SET
                    week_end          = EXCLUDED.week_end,
                    total_spent       = EXCLUDED.total_spent,
                    category_breakdown = EXCLUDED.category_breakdown,
                    trends            = EXCLUDED.trends,
                    insights          = EXCLUDED.insights,
                    created_at        = NOW()
                RETURNING id, created_at
                """,
                (
                    user_id,
                    week_start,
                    week_end,
                    total,
                    json.dumps(by_category),
                    json.dumps(trends),
                    insights,
                ),
            )
            row = cur.fetchone()
            conn.commit()
    return {
        "id": row[0],
        "user_id": user_id,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_spent": total,
        "category_breakdown": by_category,
        "trends": trends,
        "insights": insights,
        "created_at": row[1].isoformat(),
    }


def generate_weekly_digest(user_id: int, ref: date | None = None) -> dict[str, Any]:
    """Build (or refresh) the weekly digest for *user_id* relative to *ref*."""
    week_start, week_end = get_week_bounds(ref)
    prev_start = week_start - timedelta(weeks=1)
    prev_end = week_end - timedelta(weeks=1)

    expenses = _fetch_expenses(user_id, week_start, week_end)
    total, by_category = _aggregate(expenses)
    prev_total = _fetch_previous_total(user_id, prev_start, prev_end)
    trends = _calculate_trends(total, by_category, prev_total)
    insights = _generate_insights(total, by_category, trends)

    return _upsert_digest(
        user_id, week_start, week_end, total, by_category, trends, insights
    )


def get_digest_history(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Return the *limit* most recent weekly digests for *user_id*."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, week_start, week_end, total_spent,
                       category_breakdown, trends, insights, created_at
                FROM weekly_digest
                WHERE user_id = %s
                ORDER BY week_start DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

    results = []
    for row in rows:
        record = dict(zip(cols, row))
        record["week_start"] = record["week_start"].isoformat()
        record["week_end"] = record["week_end"].isoformat()
        record["total_spent"] = float(record["total_spent"])
        record["created_at"] = record["created_at"].isoformat()
        results.append(record)
    return results
