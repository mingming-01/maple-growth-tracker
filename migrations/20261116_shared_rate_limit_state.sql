-- AI/Nexon 공유 요청 제한 상태. 운영 DB에는 명시적으로 적용한다.
CREATE TABLE IF NOT EXISTS public.shared_rate_limit_state (
    bucket_key TEXT PRIMARY KEY,
    timestamps DOUBLE PRECISION[] NOT NULL DEFAULT '{}'::DOUBLE PRECISION[],
    daily_count INTEGER NOT NULL DEFAULT 0,
    daily_date DATE,
    next_allowed_at DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shared_rate_limit_updated_at
    ON public.shared_rate_limit_state (updated_at);

ALTER TABLE public.shared_rate_limit_state ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.shared_rate_limit_state
    FROM PUBLIC, anon, authenticated;
