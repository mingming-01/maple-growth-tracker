"""Session-protected admin JSON API tests for the React operations dashboard."""
import unittest
from datetime import datetime, timezone
import tempfile
from pathlib import Path

import app as tracker
from tracker import create_app
from tracker.runtime import get_runtime_state


class AdminLogsReactApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        })
        self.temp_dir = tempfile.TemporaryDirectory()
        with self.app.app_context():
            self.state = get_runtime_state()
            self.state.log_db_path = str(Path(self.temp_dir.name) / "admin_logs.sqlite3")
            self.state.log_db_backend = "sqlite"
            self.state.log_storage_warning = ""
            tracker.initialize_log_db()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_authenticated"] = True
            session["csrf_token"] = "react-api-test-token"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_logs_json_api_uses_session_auth_and_filters(self):
        with self.app.app_context():
            tracker.log_action(
                "캐릭터 조회", character_name="밍득", world_name="크로아",
                result="성공", path="/api/character", status_code=200, duration_ms=42
            )
            tracker.log_action(
                "성장 기록 조회", character_name="테스트캐릭터",
                result="실패", path="/api/history", status_code=503,
                duration_ms=250, error_type="http_5xx"
            )

        response = self.client.get("/admin/api/logs?q=테스트캐릭터&result=실패")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["totalCount"], 1)
        self.assertEqual(payload["displayedCount"], 1)
        self.assertEqual(payload["logs"][0]["character_name"], "테스트캐릭터")
        self.assertEqual(payload["logs"][0]["error_type"], "http_5xx")
        self.assertTrue(payload["csrfToken"])
        self.assertEqual(payload["storageBackend"], "sqlite")

    def test_admin_logs_json_api_requires_authenticated_session(self):
        anonymous = self.app.test_client()
        response = anonymous.get("/admin/api/logs")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
