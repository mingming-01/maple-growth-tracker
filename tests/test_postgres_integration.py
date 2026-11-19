"""격리된 PostgreSQL에서 저장·복원·공유 제한·동시성을 검증한다."""
import os
from pathlib import Path

import psycopg
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

from tracker.repositories.growth_history_store import GrowthHistoryStore


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@unittest.skipUnless(POSTGRES_URL, "TEST_POSTGRES_URL is not configured")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(POSTGRES_URL, autocommit=True) as connection:
            for role in ("anon", "authenticated"):
                try:
                    connection.execute(f"CREATE ROLE {role} NOLOGIN")
                except psycopg.errors.DuplicateObject:
                    pass
            # 현재 운영 DB의 업그레이드 경로를 재현하기 위해 출처 컬럼이 없는 구형 테이블을 만든다.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS public.growth_daily_snapshots (
                    ocid TEXT NOT NULL,
                    snapshot_date DATE NOT NULL,
                    character_name TEXT NOT NULL,
                    world_name TEXT,
                    level INTEGER,
                    experience NUMERIC(30, 0),
                    ranking INTEGER,
                    ranking_scope TEXT,
                    ranking_source_date DATE,
                    experience_rate NUMERIC(7, 4),
                    experience_rate_checked BOOLEAN NOT NULL DEFAULT FALSE,
                    record_status TEXT NOT NULL
                        CHECK (record_status IN ('available', 'not_ready')),
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ocid, snapshot_date)
                )
                """
            )
            migration = Path("migrations/20261116_shared_rate_limit_state.sql").read_text(
                encoding="utf-8"
            )
            connection.execute(migration)
        cls.store = GrowthHistoryStore(
            database_url=POSTGRES_URL,
            sqlite_path="instance/postgres-integration-unused.sqlite3",
        )
        cls.store.initialize()

    def test_growth_records_persist_and_restore_across_repository_instances(self):
        ocid = "integration-" + uuid4().hex
        records = [{
            "date": date.today().isoformat(),
            "level": 280,
            "experience": 123456,
            "ranking": 321,
            "rankingScope": "overall",
            "rankingSourceDate": date.today().isoformat(),
            "growthSource": "ranking/overall",
            "growthObservedAt": "2026-11-19T10:00:00+00:00",
            "recordStatus": "available",
        }]
        self.store.save_records(ocid, "통합테스트", "테스트월드", records)

        restored = GrowthHistoryStore(database_url=POSTGRES_URL)
        result = restored.get_records(ocid, date.today(), date.today())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["experience"], 123456)
        self.assertEqual(result[0]["ranking"], 321)
        self.assertEqual(result[0]["rankingScope"], "overall")
        self.assertEqual(result[0]["rankingSourceDate"], date.today().isoformat())
        self.assertEqual(result[0]["growthSource"], "ranking/overall")
        self.assertEqual(result[0]["growthObservedAt"], "2026-11-19T10:00:00+00:00")
        self.assertEqual(result[0]["recordStatus"], "available")

    def test_ai_daily_limits_are_shared_and_atomic_under_concurrency(self):
        client_key = uuid4().hex
        today = date.today().isoformat()

        def consume(_):
            return self.store.consume_ai_rate_limit(
                client_key=client_key,
                now=1_800_000_000.0,
                today=today,
                per_minute_limit=100,
                per_ip_daily_limit=3,
                global_daily_limit=100,
                retry_after_midnight=3600,
            )[0]

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(consume, range(8)))

        self.assertEqual(sum(results), 3)

    def test_nexon_reservations_are_monotonic_across_connections(self):
        now = 1_800_000_000.0
        first = self.store.reserve_nexon_request_slot(now, 0.25)
        second = self.store.reserve_nexon_request_slot(now, 0.25)

        self.assertGreaterEqual(first, 0.0)
        self.assertGreaterEqual(second - first, 0.24)


if __name__ == "__main__":
    unittest.main()
