-- API fallback snapshots are only accessed by the server-side database role.
CREATE TABLE IF NOT EXISTS public.api_snapshots (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_snapshots_saved_at
    ON public.api_snapshots (saved_at DESC);

ALTER TABLE public.api_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.api_snapshots FROM PUBLIC, anon, authenticated;
