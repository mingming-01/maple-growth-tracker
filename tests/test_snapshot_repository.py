"""Tests for SQLite and PostgreSQL API snapshot persistence."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        init_connection = MagicMock()
        save_connection = MagicMock()
        save_connection.execute.return_value.rowcount = 1
        load_connection = MagicMock()
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

    def test_sqlite_insert_only_snapshot_does_not_replace_existing_payload(self):
        initialize_snapshot_db(self.path)
        self.assertTrue(
            save_api_snapshot(self.path, "character:test", {"level": 280})
        )

        # Existing snapshot must win over a partial response.
        self.assertIsNone(
            save_api_snapshot(
                self.path,
                "character:test",
                {"level": 1, "rankingDataStatus": "partial"},
                only_if_missing=True,
            )
        )
        loaded, _ = load_api_snapshot(self.path, "character:test")
        self.assertEqual(loaded, {"level": 280})

        # A partial response may seed the key if no previous snapshot exists.
        self.assertTrue(
            save_api_snapshot(
                self.path,
                "character:new",
                {"level": 281, "rankingDataStatus": "partial"},
                only_if_missing=True,
            )
        )
        loaded, _ = load_api_snapshot(self.path, "character:new")
        self.assertEqual(loaded["level"], 281)

    @patch("tracker.repositories.api_snapshot_repository.psycopg.connect")
    def test_postgres_insert_only_snapshot_uses_do_nothing_on_conflict(self, connect):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        connection.execute.return_value.rowcount = 0
        connect.return_value = connection

        result = save_api_snapshot(
            self.path,
            "character:postgres",
            {"level": 1, "rankingDataStatus": "partial"},
            "postgresql://example.invalid/database",
            "postgres",
            only_if_missing=True,
        )

        self.assertIsNone(result)
        query = connection.execute.call_args.args[0]
        self.assertIn("ON CONFLICT (cache_key) DO NOTHING", query)
        self.assertEqual(connect.call_count, 1)

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
