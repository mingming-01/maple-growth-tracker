"""Tests for SQLite and PostgreSQL API snapshot persistence."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import psycopg

from tracker.repositories.api_snapshot_repository import (
    initialize_snapshot_db,
    load_api_snapshot,
    save_api_snapshot,
)


class ApiSnapshotRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp_dir.name) / "snapshots.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sqlite_snapshot_round_trip(self):
        backend, warning = initialize_snapshot_db(self.path)
        self.assertEqual(backend, "sqlite")
        self.assertEqual(warning, "")
        payload = {"characterName": "테스트캐릭터", "level": 300}

        self.assertTrue(save_api_snapshot(self.path, "character:test", payload))
        loaded, saved_at = load_api_snapshot(self.path, "character:test")

        self.assertEqual(loaded, payload)
        self.assertIsNotNone(saved_at)

    @patch("tracker.repositories.api_snapshot_repository.psycopg.connect")
    def test_postgres_snapshot_round_trip(self, connect):
        init_connection = Mock()
        save_connection = Mock()
        load_connection = Mock()
        for connection in (init_connection, save_connection, load_connection):
            connection.__enter__.return_value = connection
            connection.__exit__.return_value = False
        saved_at = datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc)
        load_connection.execute.return_value.fetchone.return_value = (
            json.dumps({"characterName": "Postgres", "level": 300}),
            saved_at,
        )
        connect.side_effect = [init_connection, save_connection, load_connection]

        backend, warning = initialize_snapshot_db(
            self.path, "postgresql://example.invalid/database"
        )
        self.assertEqual(backend, "postgres")
        self.assertEqual(warning, "")
        self.assertTrue(save_api_snapshot(
            self.path,
            "character:postgres",
            {"characterName": "Postgres", "level": 300},
            "postgresql://example.invalid/database",
            "postgres",
        ))
        loaded, loaded_at = load_api_snapshot(
            self.path,
            "character:postgres",
            "postgresql://example.invalid/database",
            "postgres",
        )

        self.assertEqual(loaded, {"characterName": "Postgres", "level": 300})
        self.assertEqual(loaded_at, saved_at.isoformat(timespec="seconds"))
        self.assertEqual(connect.call_count, 3)

    @patch("tracker.repositories.api_snapshot_repository.psycopg.connect")
    def test_postgres_initialization_failure_falls_back_to_sqlite(self, connect):
        connect.side_effect = psycopg.OperationalError("database unavailable")
        backend, warning = initialize_snapshot_db(
            self.path, "postgresql://example.invalid/database"
        )
        self.assertEqual(backend, "sqlite")
        self.assertIn("PostgreSQL", warning)
        self.assertTrue(Path(self.path).exists())


if __name__ == "__main__":
    unittest.main()
