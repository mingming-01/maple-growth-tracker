import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import app as tracker
from tracker.controller import admin_controller


class AdminLogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp_dir.name) / "admin_logs.sqlite3"
        self.path_patch = patch.object(tracker, "LOG_DB_PATH", str(self.log_path))
        self.backend_patch = patch.object(tracker, "LOG_DB_BACKEND", "sqlite")
        self.warning_patch = patch.object(tracker, "LOG_STORAGE_WARNING", "")
        self.controller_backend_patch = patch.object(admin_controller, "LOG_DB_BACKEND", "sqlite")
        self.controller_warning_patch = patch.object(admin_controller, "LOG_STORAGE_WARNING", "")
        self.path_patch.start()
        self.backend_patch.start()
        self.warning_patch.start()
        self.controller_backend_patch.start()
        self.controller_warning_patch.start()
        tracker.initialize_log_db()

        self.client = tracker.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_authenticated"] = True
            session["csrf_token"] = "test-token"

    def tearDown(self):
        self.controller_warning_patch.stop()
        self.controller_backend_patch.stop()
        self.warning_patch.stop()
        self.backend_patch.stop()
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_log_action_saves_request_details(self):
        tracker.log_action(
            "캐릭터 조회",
            character_name="밍득",
            world_name="크로아",
            result="성공",
            path="/api/character",
            status_code=200,
            duration_ms=42,
        )

        connection = tracker.connect_log_db()
        try:
            row = connection.execute(
                "SELECT action, character_name, world_name, path, status_code, "
                "duration_ms, error_type FROM action_logs"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(row["action"], "캐릭터 조회")
        self.assertEqual(row["character_name"], "밍득")
        self.assertEqual(row["path"], "/api/character")
        self.assertEqual(row["status_code"], 200)
        self.assertEqual(row["duration_ms"], 42)
        self.assertIsNone(row["error_type"])

    def test_admin_log_filters_by_character_and_result(self):
        tracker.log_action(
            "캐릭터 조회",
            character_name="밍득",
            result="성공",
            path="/api/character",
            status_code=200,
            duration_ms=25,
        )
        tracker.log_action(
            "성장 기록 조회",
            character_name="테스트캐릭터",
            result="실패",
            path="/api/history",
            status_code=503,
            duration_ms=250,
            error_type="http_5xx",
        )

        response = self.client.get("/admin/logs?q=테스트캐릭터&result=실패")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("테스트캐릭터", page)
        self.assertIn("http_5xx", page)
        self.assertNotIn("밍득", page)
        self.assertIn("검색 결과 1 / 1건", page)

    def test_admin_log_time_uses_korean_timezone(self):
        timestamp = datetime(2026, 10, 27, 7, 6, 22, tzinfo=timezone.utc)
        self.assertEqual(
            tracker.format_admin_log_time(timestamp),
            "2026-10-27 (화) 16:06:22 KST",
        )

        tracker.log_action(
            "캐릭터 조회",
            character_name="밍득",
            result="성공",
            path="/api/character",
            status_code=200,
            duration_ms=25,
        )
        response = self.client.get("/admin/logs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("KST", response.get_data(as_text=True))
        self.assertIn("시간 (한국 시간)", response.get_data(as_text=True))

    def test_admin_logs_show_sqlite_storage_warning(self):
        response = self.client.get("/admin/logs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("SQLite", response.get_data(as_text=True))
        self.assertIn("재배포 후 보존", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
