"""API 응답 스냅샷의 PostgreSQL 우선 저장과 SQLite 개발 폴백을 담당한다."""
import json
import sqlite3
from datetime import datetime
import time
import psycopg

from tracker.services.performance_metrics import increment_metric, observe_metric


def _connect_postgres(database_url):
    started_at = time.perf_counter()
    try:
        return psycopg.connect(database_url, connect_timeout=3, sslmode="require", prepare_threshold=None)
    finally:
        increment_metric("db.connection_attempts", backend="postgres", store="snapshots")
        observe_metric(
            "db.connection_ms",
            (time.perf_counter() - started_at) * 1000,
            backend="postgres",
            store="snapshots",
        )


def _connect_sqlite(db_path):
    started_at = time.perf_counter()
    try:
        return sqlite3.connect(db_path, timeout=5)
    finally:
        increment_metric("db.connection_attempts", backend="sqlite", store="snapshots")
        observe_metric(
            "db.connection_ms",
            (time.perf_counter() - started_at) * 1000,
            backend="sqlite",
            store="snapshots",
        )


def _initialize_sqlite(db_path):
    connection = _connect_sqlite(db_path)
    try:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS api_snapshots (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                )
            """)
    finally:
        connection.close()


def initialize_snapshot_db(db_path, database_url=""):
    """PostgreSQL을 우선 사용하고 연결할 수 없으면 SQLite로 폴백한다."""
    if database_url:
        try:
            connection = _connect_postgres(database_url)
            try:
                with connection:
                    connection.execute("""
                        CREATE TABLE IF NOT EXISTS api_snapshots (
                            cache_key TEXT PRIMARY KEY,
                            payload TEXT NOT NULL,
                            saved_at TIMESTAMPTZ NOT NULL
                        )
                    """)
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS idx_api_snapshots_saved_at "
                        "ON api_snapshots (saved_at DESC)"
                    )
                    connection.execute("ALTER TABLE api_snapshots ENABLE ROW LEVEL SECURITY")
                    connection.execute(
                        "REVOKE ALL ON TABLE api_snapshots FROM PUBLIC, anon, authenticated"
                    )
            finally:
                connection.close()
            return "postgres", ""
        except psycopg.Error:
            _initialize_sqlite(db_path)
            return "sqlite", (
                "PostgreSQL 스냅샷 저장소 연결에 실패해 SQLite를 사용 중입니다. "
                "Render 재배포 후 스냅샷이 유지되지 않을 수 있습니다."
            )

    _initialize_sqlite(db_path)
    return "sqlite", ""


def save_api_snapshot(db_path, cache_key, data, database_url="", backend="sqlite"):
    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = json.dumps(data, ensure_ascii=False)
    operation_started = time.perf_counter()
    try:
        if backend == "postgres":
            connection = _connect_postgres(database_url)
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO api_snapshots (cache_key, payload, saved_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            payload = EXCLUDED.payload,
                            saved_at = CURRENT_TIMESTAMP
                        """,
                        (cache_key, payload),
                    )
            finally:
                connection.close()
        else:
            connection = _connect_sqlite(db_path)
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO api_snapshots (cache_key, payload, saved_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(cache_key) DO UPDATE SET
                            payload = excluded.payload,
                            saved_at = excluded.saved_at
                        """,
                        (cache_key, payload, saved_at),
                    )
            finally:
                connection.close()
        return saved_at
    except (sqlite3.Error, psycopg.Error):
        print("성장 데이터 스냅샷 저장에 실패했습니다.")
        return None
    finally:
        increment_metric("db.operations", operation="snapshot.upsert")
        increment_metric("db.sql_statements", operation="snapshot.upsert")
        observe_metric(
            "db.operation_ms",
            (time.perf_counter() - operation_started) * 1000,
            operation="snapshot.upsert",
        )


def load_api_snapshot(db_path, cache_key, database_url="", backend="sqlite"):
    operation_started = time.perf_counter()
    try:
        if backend == "postgres":
            connection = _connect_postgres(database_url)
            try:
                with connection:
                    row = connection.execute(
                        "SELECT payload, saved_at FROM api_snapshots WHERE cache_key = %s",
                        (cache_key,),
                    ).fetchone()
            finally:
                connection.close()
        else:
            connection = _connect_sqlite(db_path)
            try:
                with connection:
                    row = connection.execute(
                        "SELECT payload, saved_at FROM api_snapshots WHERE cache_key = ?",
                        (cache_key,),
                    ).fetchone()
            finally:
                connection.close()
        if not row:
            return None, None
        saved_at = row[1].isoformat(timespec="seconds") if hasattr(row[1], "isoformat") else row[1]
        return json.loads(row[0]), saved_at
    except (sqlite3.Error, psycopg.Error, ValueError, TypeError):
        print("성장 데이터 스냅샷을 불러오지 못했습니다.")
        return None, None
    finally:
        increment_metric("db.operations", operation="snapshot.select")
        increment_metric("db.sql_statements", operation="snapshot.select")
        observe_metric(
            "db.operation_ms",
            (time.perf_counter() - operation_started) * 1000,
            operation="snapshot.select",
        )
