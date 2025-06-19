-- Diary table: Single source of truth for all events
-- Using DuckDB (already in production per user confirmation)

CREATE SEQUENCE IF NOT EXISTS diary_seq START 1;

CREATE TABLE IF NOT EXISTS diary (
    id INTEGER PRIMARY KEY DEFAULT nextval('diary_seq'),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entry_type TEXT CHECK(entry_type IN ('trade', 'message', 'response')),
    user_id BIGINT NOT NULL,
    wallet_address TEXT,
    data JSON NOT NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_diary_user_time ON diary(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_diary_wallet_time ON diary(wallet_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_diary_type_time ON diary(entry_type, timestamp DESC);

-- Note: Using sequence for DuckDB compatibility
-- JSON data field stores all event-specific data 