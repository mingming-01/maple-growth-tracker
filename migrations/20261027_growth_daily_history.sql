-- Run once in the Supabase SQL Editor, or let the application create this table
-- automatically when GROWTH_DATABASE_URL is configured.
CREATE TABLE IF NOT EXISTS growth_daily_snapshots (
    ocid TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    character_name TEXT NOT NULL,
    world_name TEXT,
    level INTEGER,
    experience NUMERIC(30, 0),
    ranking INTEGER,
    record_status TEXT NOT NULL
        CHECK (record_status IN ('available', 'not_ready')),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ocid, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_growth_daily_name_date
    ON growth_daily_snapshots (character_name, snapshot_date DESC);
