"""Persistent storage for daily MapleStory ranking snapshots.

GROWTH_DATABASE_URL points to PostgreSQL (for example, a Supabase connection
string). Without it, the application uses a local SQLite file for development.
"""
from datetime import date
from pathlib import Path
import sqlite3

import psycopg


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

    @property
    def uses_postgres(self):
        return self.backend == "postgres"

    def _connect(self):
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

    def initialize(self):
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
                            record_status TEXT NOT NULL
                                CHECK (record_status IN ('available', 'not_ready')),
                            recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocid, snapshot_date)
                        )
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
                            record_status TEXT NOT NULL
                                CHECK (record_status IN ('available', 'not_ready')),
                            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (ocid, snapshot_date)
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_growth_daily_name_date
                        ON growth_daily_snapshots (character_name, snapshot_date DESC)
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
                     experience, ranking, record_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ocid, snapshot_date) DO UPDATE SET
                    character_name = EXCLUDED.character_name,
                    world_name = EXCLUDED.world_name,
                    level = EXCLUDED.level,
                    experience = EXCLUDED.experience,
                    ranking = EXCLUDED.ranking,
                    record_status = EXCLUDED.record_status,
                    recorded_at = CURRENT_TIMESTAMP
                WHERE growth_daily_snapshots.record_status <> 'available'
                   OR EXCLUDED.record_status = 'available'
            """
        else:
            query = """
                INSERT INTO growth_daily_snapshots
                    (ocid, snapshot_date, character_name, world_name, level,
                     experience, ranking, record_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ocid, snapshot_date) DO UPDATE SET
                    character_name = excluded.character_name,
                    world_name = excluded.world_name,
                    level = excluded.level,
                    experience = excluded.experience,
                    ranking = excluded.ranking,
                    record_status = excluded.record_status,
                    recorded_at = CURRENT_TIMESTAMP
                WHERE growth_daily_snapshots.record_status <> 'available'
                   OR excluded.record_status = 'available'
            """

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
        return len(rows)

    def get_records(self, ocid, start_date, end_date):
        self.initialize()
        start = date.fromisoformat(str(start_date))
        end = date.fromisoformat(str(end_date))
        placeholder = "%s" if self.uses_postgres else "?"
        query = f"""
            SELECT snapshot_date, character_name, world_name, level,
                   experience, ranking, record_status, recorded_at
            FROM growth_daily_snapshots
            WHERE ocid = {placeholder} AND snapshot_date >= {placeholder}
              AND snapshot_date <= {placeholder}
            ORDER BY snapshot_date ASC
        """
        connection = self._connect()
        try:
            rows = connection.execute(query, (str(ocid), start, end)).fetchall()
        finally:
            connection.close()

        result = []
        for row in rows:
            snapshot_date, saved_name, saved_world, level, experience, ranking, status, recorded_at = row
            result.append({
                "date": snapshot_date.isoformat() if hasattr(snapshot_date, "isoformat") else str(snapshot_date),
                "characterName": saved_name,
                "worldName": saved_world,
                "level": self._to_integer(level),
                "experience": self._to_integer(experience),
                "ranking": self._to_integer(ranking),
                "recordStatus": status,
                "recordedAt": recorded_at.isoformat() if hasattr(recorded_at, "isoformat") else str(recorded_at),
            })
        return result
