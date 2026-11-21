"""Shared provider cooldown state for multi-worker deployments."""
import sqlite3
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from tracker.repositories.postgres_connection_pool import get_pooled_connection


class AIProviderStateStore:
    """Persist provider cooldowns in PostgreSQL or the local SQLite instance DB."""

    def __init__(self, database_url=None, sqlite_path="instance/ai_provider_state.sqlite3"):
        self.database_url = (database_url or "").strip()
        self.sqlite_path = str(sqlite_path)
        self.uses_postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        self._initialized = False
        self._lock = Lock()

    def _connect(self):
        if self.uses_postgres:
            host = urlparse(self.database_url).hostname
            sslmode = "disable" if host in ("localhost", "127.0.0.1", "::1") else "require"
            return get_pooled_connection(
                self.database_url,
                connect_timeout=3,
                sslmode=sslmode,
                prepare_threshold=None,
                store="ai_provider_state",
            )
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.sqlite_path, timeout=2)

    def initialize(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            connection = self._connect()
            try:
                with connection:
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS ai_provider_state (
                            provider_key TEXT PRIMARY KEY,
                            cooldown_until DOUBLE PRECISION NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )""" if self.uses_postgres else
                        """CREATE TABLE IF NOT EXISTS ai_provider_state (
                            provider_key TEXT PRIMARY KEY,
                            cooldown_until REAL NOT NULL,
                            updated_at REAL NOT NULL
                        )"""
                    )
                    if self.uses_postgres:
                        connection.execute("ALTER TABLE ai_provider_state ENABLE ROW LEVEL SECURITY")
                        connection.execute("REVOKE ALL ON TABLE ai_provider_state FROM PUBLIC, anon, authenticated")
                self._initialized = True
            finally:
                connection.close()

    def get_cooldown_until(self, provider_key):
        self.initialize()
        connection = self._connect()
        try:
            marker = "%s" if self.uses_postgres else "?"
            row = connection.execute(
                f"SELECT cooldown_until FROM ai_provider_state WHERE provider_key = {marker}",
                (provider_key,),
            ).fetchone()
            return float(row[0]) if row else 0.0
        finally:
            connection.close()

    def set_cooldown_until(self, provider_key, cooldown_until):
        self.initialize()
        connection = self._connect()
        try:
            with connection:
                if self.uses_postgres:
                    connection.execute(
                        """INSERT INTO ai_provider_state (provider_key, cooldown_until)
                        VALUES (%s, %s)
                        ON CONFLICT (provider_key) DO UPDATE SET
                            cooldown_until = GREATEST(ai_provider_state.cooldown_until, EXCLUDED.cooldown_until),
                            updated_at = CURRENT_TIMESTAMP""",
                        (provider_key, float(cooldown_until)),
                    )
                else:
                    connection.execute(
                        """INSERT INTO ai_provider_state (provider_key, cooldown_until, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT (provider_key) DO UPDATE SET
                            cooldown_until = MAX(ai_provider_state.cooldown_until, excluded.cooldown_until),
                            updated_at = excluded.updated_at""",
                        (provider_key, float(cooldown_until), time.time()),
                    )
        finally:
            connection.close()

    def clear_cooldown(self, provider_key):
        self.initialize()
        connection = self._connect()
        try:
            with connection:
                marker = "%s" if self.uses_postgres else "?"
                connection.execute(f"DELETE FROM ai_provider_state WHERE provider_key = {marker}", (provider_key,))
        finally:
            connection.close()
