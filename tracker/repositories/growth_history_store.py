"""Persistent storage for daily MapleStory ranking snapshots.

GROWTH_DATABASE_URL points to PostgreSQL (for example, a Supabase connection
string). Without it, the application uses a local SQLite file for development.
"""
from datetime import date
import json
import math
from pathlib import Path
import sqlite3
from threading import Lock
import time

import psycopg
from tracker.services.performance_metrics import increment_metric, observe_metric


class GrowthHistoryStore:
    def __init__(self, database_url=None, sqlite_path="instance/growth_history.sqlite3"):
        self.database_url = (database_url or "").strip()
        self.sqlite_path = str(sqlite_path)
        if not self.database_url:
            self.backend = "sqlite"
        elif self.database_url.startswith(("postgres://", "postgresql://")):
            self.backend = "postgres"
        else:
            self.backend = "invalid"
        self._initialized = False
        self._initialize_lock = Lock()

    @property
    def uses_postgres(self):
        return self.backend == "postgres"

    def _connect(self):
        started_at = time.perf_counter()
        try:
            if self.backend == "postgres":
                return psycopg.connect(
                    self.database_url,
                    connect_timeout=3,
                    sslmode="require",
                    prepare_threshold=None,
                )
            if self.backend != "sqlite":
                raise ValueError("GROWTH_DATABASE_URL must be a PostgreSQL connection string.")

            Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(self.sqlite_path, timeout=5)
        finally:
            increment_metric("db.connections", backend=self.backend, store="growth_history")
            observe_metric(
                "db.connection_ms",
                (time.perf_counter() - started_at) * 1000,
                backend=self.backend,
                store="growth_history",
            )

    def initialize(self):
        with self._initialize_lock:
            return self._initialize_once()

    def _initialize_once(self):
        if self._initialized:
            return

        connection = self._connect()
        try:
            with connection:
                if self.uses_postgres:
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS growth_daily_snapshots (
                            ocid TEXT NOT NULL,
                            snapshot_date DATE NOT NULL,
                            character_name TEXT NOT NULL,
                            world_name TEXT,
                            level INTEGER,
                            experience NUMERIC(30, 0),
                            ranking INTEGER,
                            experience_rate NUMERIC(7, 4),
                            experience_rate_checked BOOLEAN NOT NULL DEFAULT FALSE,
                            record_status TEXT NOT NULL
                                CHECK (record_status IN ('available', 'not_ready')),
                            recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocid, snapshot_date)
                        )
                        """
                    )
                    connection.execute(
                        """
                        ALTER TABLE growth_daily_snapshots
                        ADD COLUMN IF NOT EXISTS experience_rate NUMERIC(7, 4)
                        """
                    )
                    connection.execute(
                        """
                        ALTER TABLE growth_daily_snapshots
                        ADD COLUMN IF NOT EXISTS experience_rate_checked BOOLEAN NOT NULL DEFAULT FALSE
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_growth_daily_name_date
                        ON growth_daily_snapshots (character_name, snapshot_date DESC)
                        """
                    )
                    connection.execute(
                        "ALTER TABLE growth_daily_snapshots ENABLE ROW LEVEL SECURITY"
                    )
                    connection.execute(
                        """
                        REVOKE ALL ON TABLE growth_daily_snapshots
                        FROM PUBLIC, anon, authenticated
                        """
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS api_request_limit_state (
                            client_key TEXT PRIMARY KEY,
                            request_timestamps DOUBLE PRECISION[] NOT NULL DEFAULT '{}'::DOUBLE PRECISION[],
                            refresh_timestamps DOUBLE PRECISION[] NOT NULL DEFAULT '{}'::DOUBLE PRECISION[],
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_api_request_limit_updated_at
                        ON api_request_limit_state (updated_at)
                        """
                    )
                    connection.execute(
                        "ALTER TABLE api_request_limit_state ENABLE ROW LEVEL SECURITY"
                    )
                    connection.execute(
                        """
                        REVOKE ALL ON TABLE api_request_limit_state
                        FROM PUBLIC, anon, authenticated
                        """
                    )
                else:
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS growth_daily_snapshots (
                            ocid TEXT NOT NULL,
                            snapshot_date DATE NOT NULL,
                            character_name TEXT NOT NULL,
                            world_name TEXT,
                            level INTEGER,
                            experience NUMERIC,
                            ranking INTEGER,
                            experience_rate REAL,
                            experience_rate_checked INTEGER NOT NULL DEFAULT 0,
                            record_status TEXT NOT NULL
                                CHECK (record_status IN ('available', 'not_ready')),
                            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocid, snapshot_date)
                        )
                        """
                    )
                    columns = {
                        row[1] for row in connection.execute(
                            "PRAGMA table_info(growth_daily_snapshots)"
                        ).fetchall()
                    }
                    if "experience_rate" not in columns:
                        connection.execute(
                            "ALTER TABLE growth_daily_snapshots ADD COLUMN experience_rate REAL"
                        )
                    if "experience_rate_checked" not in columns:
                        connection.execute(
                            "ALTER TABLE growth_daily_snapshots "
                            "ADD COLUMN experience_rate_checked INTEGER NOT NULL DEFAULT 0"
                        )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_growth_daily_name_date
                        ON growth_daily_snapshots (character_name, snapshot_date DESC)
                        """
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS api_request_limit_state (
                            client_key TEXT PRIMARY KEY,
                            request_timestamps TEXT NOT NULL DEFAULT '[]',
                            refresh_timestamps TEXT NOT NULL DEFAULT '[]',
                            updated_at REAL NOT NULL
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_api_request_limit_updated_at
                        ON api_request_limit_state (updated_at)
                        """
                    )
            self._initialized = True
        finally:
            connection.close()

    @staticmethod
    def _to_integer(value):
        if value is None or value == "":
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_rate(value):
        if value is None or value == "":
            return None
        try:
            number = float(str(value).replace("%", "").replace(",", "").strip())
        except (TypeError, ValueError):
            return None
        if not 0 <= number <= 100:
            return None
        return number

    @classmethod
    def _normalize_record(cls, ocid, character_name, world_name, record):
        if not isinstance(record, dict):
            return None

        status = record.get("recordStatus")
        try:
            snapshot_date = date.fromisoformat(str(record.get("date", "")))
        except (TypeError, ValueError):
            return None

        if status == "available":
            level = cls._to_integer(record.get("level"))
            experience = cls._to_integer(record.get("experience"))
            if level is None or experience is None:
                return None
            return (
                str(ocid),
                snapshot_date.isoformat(),
                str(character_name),
                world_name,
                level,
                experience,
                cls._to_integer(record.get("ranking")),
                cls._to_rate(record.get("experienceRate")),
                bool(record.get("experienceRateChecked", False)),
                "available",
            )

        # An empty API response is recorded to avoid repeatedly requesting old dates.
        # It must never replace an already saved valid snapshot.
        if status == "not_ready":
            return (
                str(ocid),
                snapshot_date.isoformat(),
                str(character_name),
                world_name,
                None,
                None,
                None,
                None,
                False,
                "not_ready",
            )
        return None

    def save_records(self, ocid, character_name, world_name, records):
        self.initialize()
        rows = [
            normalized
            for record in records
            if (normalized := self._normalize_record(ocid, character_name, world_name, record))
        ]
        if not rows:
            return 0

        if self.uses_postgres:
            query = """
                INSERT INTO growth_daily_snapshots
                    (ocid, snapshot_date, character_name, world_name, level,
                     experience, ranking, experience_rate, experience_rate_checked, record_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ocid, snapshot_date) DO UPDATE SET
                    character_name = EXCLUDED.character_name,
                    world_name = EXCLUDED.world_name,
                    level = EXCLUDED.level,
                    experience = EXCLUDED.experience,
                    ranking = EXCLUDED.ranking,
                    experience_rate = EXCLUDED.experience_rate,
                    experience_rate_checked = EXCLUDED.experience_rate_checked,
                    record_status = EXCLUDED.record_status,
                    recorded_at = CURRENT_TIMESTAMP
                WHERE growth_daily_snapshots.record_status <> 'available'
                   OR EXCLUDED.record_status = 'available'
            """
        else:
            query = """
                INSERT INTO growth_daily_snapshots
                    (ocid, snapshot_date, character_name, world_name, level,
                     experience, ranking, experience_rate, experience_rate_checked, record_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ocid, snapshot_date) DO UPDATE SET
                    character_name = excluded.character_name,
                    world_name = excluded.world_name,
                    level = excluded.level,
                    experience = excluded.experience,
                    ranking = excluded.ranking,
                    experience_rate = excluded.experience_rate,
                    experience_rate_checked = excluded.experience_rate_checked,
                    record_status = excluded.record_status,
                    recorded_at = CURRENT_TIMESTAMP
                WHERE growth_daily_snapshots.record_status <> 'available'
                   OR excluded.record_status = 'available'
            """

        operation_started = time.perf_counter()
        connection = self._connect()
        try:
            with connection:
                if self.uses_postgres:
                    with connection.cursor() as cursor:
                        cursor.executemany(query, rows)
                else:
                    connection.executemany(query, rows)
        finally:
            connection.close()
            increment_metric("db.operations", operation="growth_history.upsert")
            increment_metric("db.sql_statements", len(rows), operation="growth_history.upsert")
            observe_metric(
                "db.operation_ms",
                (time.perf_counter() - operation_started) * 1000,
                operation="growth_history.upsert",
            )
        return len(rows)

    def get_records(self, ocid, start_date, end_date):
        self.initialize()
        start = date.fromisoformat(str(start_date))
        end = date.fromisoformat(str(end_date))
        placeholder = "%s" if self.uses_postgres else "?"
        query = f"""
            SELECT snapshot_date, character_name, world_name, level,
                   experience, ranking, experience_rate, experience_rate_checked,
                   record_status, recorded_at
            FROM growth_daily_snapshots
            WHERE ocid = {placeholder} AND snapshot_date >= {placeholder}
              AND snapshot_date <= {placeholder}
            ORDER BY snapshot_date ASC
        """
        operation_started = time.perf_counter()
        connection = self._connect()
        try:
            rows = connection.execute(query, (str(ocid), start, end)).fetchall()
        finally:
            connection.close()
            increment_metric("db.operations", operation="growth_history.select")
            increment_metric("db.sql_statements", operation="growth_history.select")
            observe_metric(
                "db.operation_ms",
                (time.perf_counter() - operation_started) * 1000,
                operation="growth_history.select",
            )

        result = []
        for row in rows:
            snapshot_date, saved_name, saved_world, level, experience, ranking, experience_rate, experience_rate_checked, status, recorded_at = row
            result.append({
                "date": snapshot_date.isoformat() if hasattr(snapshot_date, "isoformat") else str(snapshot_date),
                "characterName": saved_name,
                "worldName": saved_world,
                "level": self._to_integer(level),
                "experience": self._to_integer(experience),
                "ranking": self._to_integer(ranking),
                "experienceRate": self._to_rate(experience_rate),
                "experienceRateChecked": bool(experience_rate_checked),
                "recordStatus": status,
                "recordedAt": recorded_at.isoformat() if hasattr(recorded_at, "isoformat") else str(recorded_at),
            })
        return result


    def consume_api_rate_limit(
        self,
        client_key,
        now,
        window_seconds,
        request_limit,
        refresh_limit,
        force_refresh=False,
        max_clients=10000,
        cleanup=False,
    ):
        """공유 DB에서 IP별 슬라이딩 윈도우를 원자적으로 확인·갱신한다.

        PostgreSQL은 client_key 행을 FOR UPDATE로 잠가 여러 Gunicorn 워커의
        동시 요청을 직렬화한다. SQLite는 로컬 테스트와 개발 환경용이다.
        """
        self.initialize()
        connection = self._connect()
        try:
            with connection:
                if self.uses_postgres:
                    connection.execute(
                        """
                        INSERT INTO api_request_limit_state (client_key)
                        VALUES (%s)
                        ON CONFLICT (client_key) DO NOTHING
                        """,
                        (client_key,),
                    )
                    row = connection.execute(
                        """
                        SELECT request_timestamps, refresh_timestamps
                        FROM api_request_limit_state
                        WHERE client_key = %s
                        FOR UPDATE
                        """,
                        (client_key,),
                    ).fetchone()
                    request_timestamps = list(row[0] or [])
                    refresh_timestamps = list(row[1] or [])
                else:
                    connection.execute(
                        """
                        INSERT INTO api_request_limit_state
                            (client_key, request_timestamps, refresh_timestamps, updated_at)
                        VALUES (?, '[]', '[]', ?)
                        ON CONFLICT (client_key) DO NOTHING
                        """,
                        (client_key, now),
                    )
                    row = connection.execute(
                        """
                        SELECT request_timestamps, refresh_timestamps
                        FROM api_request_limit_state
                        WHERE client_key = ?
                        """,
                        (client_key,),
                    ).fetchone()
                    request_timestamps = json.loads(row[0] or "[]")
                    refresh_timestamps = json.loads(row[1] or "[]")

                request_timestamps = [
                    float(stamp) for stamp in request_timestamps
                    if now - float(stamp) < window_seconds
                ]
                refresh_timestamps = [
                    float(stamp) for stamp in refresh_timestamps
                    if now - float(stamp) < window_seconds
                ]

                allowed = True
                retry_after = 0
                reason = ""
                if len(request_timestamps) >= request_limit:
                    allowed = False
                    retry_after = max(
                        1,
                        math.ceil(window_seconds - (now - request_timestamps[0])),
                    )
                    reason = "requests_per_minute"
                elif force_refresh and len(refresh_timestamps) >= refresh_limit:
                    allowed = False
                    retry_after = max(
                        1,
                        math.ceil(window_seconds - (now - refresh_timestamps[0])),
                    )
                    reason = "refreshes_per_minute"
                else:
                    request_timestamps.append(now)
                    if force_refresh:
                        refresh_timestamps.append(now)

                if self.uses_postgres:
                    connection.execute(
                        """
                        UPDATE api_request_limit_state
                        SET request_timestamps = COALESCE(%s::DOUBLE PRECISION[], ARRAY[]::DOUBLE PRECISION[]),
                            refresh_timestamps = COALESCE(%s::DOUBLE PRECISION[], ARRAY[]::DOUBLE PRECISION[]),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE client_key = %s
                        """,
                        (
                            request_timestamps or None,
                            refresh_timestamps or None,
                            client_key,
                        ),
                    )
                    if cleanup:
                        # 다른 워커의 정리 작업과 충돌하지 않도록 정리 트랜잭션은 하나만 수행한다.
                        cleanup_lock = connection.execute(
                            "SELECT pg_try_advisory_xact_lock(%s, %s)",
                            (20261110, 75),
                        ).fetchone()
                        if cleanup_lock and cleanup_lock[0]:
                            stale_seconds = max(window_seconds * 2, 120)
                            connection.execute(
                                """
                                DELETE FROM api_request_limit_state
                                WHERE updated_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                                """,
                                (stale_seconds,),
                            )
                            connection.execute(
                                """
                                DELETE FROM api_request_limit_state
                                WHERE client_key IN (
                                    SELECT client_key
                                    FROM api_request_limit_state
                                    WHERE client_key <> %s
                                    ORDER BY updated_at ASC
                                    OFFSET %s
                                )
                                """,
                                (client_key, max(0, max_clients - 1)),
                            )
                else:
                    connection.execute(
                        """
                        UPDATE api_request_limit_state
                        SET request_timestamps = ?,
                            refresh_timestamps = ?,
                            updated_at = ?
                        WHERE client_key = ?
                        """,
                        (
                            json.dumps(request_timestamps),
                            json.dumps(refresh_timestamps),
                            now,
                            client_key,
                        ),
                    )
                    if cleanup:
                        stale_seconds = max(window_seconds * 2, 120)
                        connection.execute(
                            """
                            DELETE FROM api_request_limit_state
                            WHERE updated_at < ?
                            """,
                            (now - stale_seconds,),
                        )
                        connection.execute(
                            """
                            DELETE FROM api_request_limit_state
                            WHERE client_key IN (
                                SELECT client_key
                                FROM api_request_limit_state
                                WHERE client_key <> ?
                                ORDER BY updated_at ASC
                                LIMIT -1 OFFSET ?
                            )
                            """,
                            (client_key, max(0, max_clients - 1)),
                        )

            return allowed, retry_after, reason
        finally:
            connection.close()
