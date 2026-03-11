CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_digest (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    total_spent NUMERIC(12, 2) NOT NULL DEFAULT 0,
    category_breakdown JSONB NOT NULL DEFAULT '{}',
    trends JSONB NOT NULL DEFAULT '{}',
    insights TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses (user_id, date);
CREATE INDEX IF NOT EXISTS idx_weekly_digest_user_week ON weekly_digest (user_id, week_start);
