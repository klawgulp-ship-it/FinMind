# Weekly Financial Digest

The weekly digest feature aggregates a user's expense data for a given week,
calculates week-over-week trends, and generates a plain-English insight summary.
Results are persisted in the `weekly_digest` table so historical summaries can
be retrieved without recomputation.

---

## Database Schema

### `expenses`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `user_id` | INTEGER | Foreign key to users |
| `amount` | NUMERIC(12,2) | Positive value |
| `category` | VARCHAR(100) | e.g. Food, Transport |
| `description` | TEXT | Optional |
| `date` | DATE | Transaction date |
| `created_at` | TIMESTAMP | Auto-set |

### `weekly_digest`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `user_id` | INTEGER | |
| `week_start` | DATE | Monday of the week |
| `week_end` | DATE | Sunday of the week |
| `total_spent` | NUMERIC(12,2) | Sum of expenses |
| `category_breakdown` | JSONB | `{category: amount}` |
| `trends` | JSONB | Trend metrics |
| `insights` | TEXT | Generated summary |
| `created_at` | TIMESTAMP | Auto-set |

The pair `(user_id, week_start)` is unique — re-generating a digest for the
same week performs an upsert.

---

## API Endpoints

### `POST /api/insights/weekly-digest`

Generate (or refresh) the weekly digest for a user.

**Request body (JSON)**
```json
{
  "user_id": 42,
  "ref_date": "2024-01-03"  // optional — ISO date within the target week
}
```

**Response `200`**
```json
{
  "id": 1,
  "user_id": 42,
  "week_start": "2024-01-01",
  "week_end": "2024-01-07",
  "total_spent": 250.00,
  "category_breakdown": {"Food": 150.00, "Transport": 100.00},
  "trends": {
    "week_over_week_change_pct": 10.0,
    "top_category": "Food",
    "top_category_amount": 150.00,
    "previous_week_total": 227.27
  },
  "insights": "Total spending this week: $250.00. Spending increased by 10.0% compared to last week. Highest spend category: Food ($150.00).",
  "created_at": "2024-01-08T00:00:00"
}
```

**Error responses**
| Status | Reason |
|---|---|
| 400 | `user_id` missing or `ref_date` not valid ISO date |
| 500 | Unexpected server error |

---

### `GET /api/insights/weekly-digest/history`

Retrieve stored weekly digests for a user.

**Query parameters**
| Parameter | Required | Default | Description |
|---|---|---|---|
| `user_id` | yes | — | User ID |
| `limit` | no | `10` | Max records to return |

**Response `200`** — Array of digest objects (same shape as above), ordered
from most recent to oldest.

---

## Service Layer

All business logic lives in `backend/app/services/insights.py`.

| Function | Description |
|---|---|
| `get_week_bounds(ref)` | Returns `(week_start, week_end)` for the week containing `ref` |
| `generate_weekly_digest(user_id, ref)` | Full pipeline: fetch → aggregate → trend → insight → upsert |
| `get_digest_history(user_id, limit)` | Returns stored digests from `weekly_digest` table |

---

## Running Tests

```bash
pytest backend/tests/test_insights.py -v
```
