-- Record the date from which each persisted overall ranking was fetched.
-- Existing rows remain NULL and are intentionally treated as unverified until re-collected.
ALTER TABLE growth_daily_snapshots
    ADD COLUMN IF NOT EXISTS ranking_source_date DATE;
