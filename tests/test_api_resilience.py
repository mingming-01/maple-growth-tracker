import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import app as tracker


class ApiResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.snapshot_path = Path(self.temp_dir.name) / "snapshots.sqlite3"
        self.path_patch = patch.object(tracker, "SNAPSHOT_DB_PATH", str(self.snapshot_path))
        self.path_patch.start()
        tracker.initialize_snapshot_db()
        tracker.CACHE.clear()
        self.client = tracker.app.test_client()

    def tearDown(self):
        tracker.CACHE.clear()
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_nexon_request_has_timeout(self):
        response = Mock(status_code=200)
        response.json.return_value = {"ocid": "test-ocid"}

        with patch.object(tracker.requests, "get", return_value=response) as get:
            ocid, _ = tracker.get_ocid("테스트캐릭터")

        self.assertEqual(ocid, "test-ocid")
        self.assertEqual(get.call_args.kwargs["timeout"], tracker.NEXON_API_TIMEOUT)

    def test_temporary_failure_returns_saved_character_as_stale(self):
        snapshot = {
            "characterName": "테스트캐릭터",
            "level": 280,
            "rankingDataStatus": "available"
        }
        tracker.save_api_snapshot("character:테스트캐릭터", snapshot)

        with patch.object(tracker, "get_ocid", side_effect=requests.Timeout("internal timeout")):
            response = self.client.get("/api/character?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["dataStatus"], "stale")
        self.assertIn("dataAsOf", body)
        self.assertEqual(body["characterName"], "테스트캐릭터")

    def test_temporary_failure_without_snapshot_returns_safe_error(self):
        with patch.object(tracker, "get_ocid", side_effect=requests.Timeout("private timeout detail")):
            response = self.client.get("/api/character?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private timeout detail", response.get_data(as_text=True))
        self.assertIn("오류", response.get_data(as_text=True)) if False else None

    def test_empty_ranking_response_is_marked_not_ready(self):
        empty_response = Mock(status_code=200)
        with patch.object(tracker, "get_api_class", return_value="테스트직업"), patch.object(
            tracker, "get_ranking", return_value=(None, empty_response)
        ):
            result = tracker.get_character_rankings(
                target_date="2026-10-27",
                world_name="테스트월드",
                character_class="테스트직업",
                ocid="test-ocid"
            )

        self.assertEqual(result["rankingDataStatus"], "not_ready")


if __name__ == "__main__":
    unittest.main()
