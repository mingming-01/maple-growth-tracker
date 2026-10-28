"""API 응답 스냅샷의 SQLite 저장과 조회를 담당한다."""

import json
import sqlite3
from datetime import datetime


def initialize_snapshot_db(db_path):
    connection = sqlite3.connect(db_path, timeout=5)
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


def save_api_snapshot(db_path, cache_key, data):
    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        connection = sqlite3.connect(db_path, timeout=5)
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
                    (cache_key, json.dumps(data, ensure_ascii=False), saved_at)
                )
        finally:
            connection.close()
        return saved_at
    except sqlite3.Error:
        print("성장 데이터 스냅샷 저장에 실패했습니다.")
        return None


def load_api_snapshot(db_path, cache_key):
    try:
        connection = sqlite3.connect(db_path, timeout=5)
        try:
            with connection:
                row = connection.execute(
                    "SELECT payload, saved_at FROM api_snapshots WHERE cache_key = ?",
                    (cache_key,)
                ).fetchone()
        finally:
            connection.close()
        if not row:
            return None, None
        return json.loads(row[0]), row[1]
    except (sqlite3.Error, ValueError, TypeError):
        print("성장 데이터 스냅샷을 불러오지 못했습니다.")
        return None, None
