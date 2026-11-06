import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import app as tracker
from tracker import create_app
from tracker.controller import character_controller, history_controller
from tracker.integrations import nexon_api
from tracker.runtime import get_runtime_state
from tracker.services import nexon_service


class ApiResilienceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        })
        self.temp_dir = tempfile.TemporaryDirectory()
        self.snapshot_path = Path(self.temp_dir.name) / "snapshots.sqlite3"
        with self.app.app_context():
            self.state = get_runtime_state()
            self.state.snapshot_db_path = str(self.snapshot_path)
            self.state.cache.clear()
            tracker.initialize_snapshot_db()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            self.state.cache.clear()
        self.temp_dir.cleanup()

    def save_snapshot(self, key, value):
        with self.app.app_context():
            tracker.save_api_snapshot(key, value)

    def test_nexon_request_has_timeout(self):
        response = Mock(status_code=200)
        response.json.return_value = {"ocid": "test-ocid"}

        with self.app.app_context(), patch.object(
            nexon_api, "request_with_retries", return_value=response
        ) as request:
            ocid, _ = nexon_api.get_ocid("테스트캐릭터")

        self.assertEqual(ocid, "test-ocid")
        self.assertEqual(
            request.call_args.kwargs["timeout"],
            (
                self.app.config["NEXON_API_CONNECT_TIMEOUT"],
                self.app.config["NEXON_API_READ_TIMEOUT"],
            ),
        )

    def test_temporary_failure_returns_saved_character_as_stale(self):
        self.save_snapshot("character:테스트캐릭터", {
            "characterName": "테스트캐릭터",
            "level": 280,
            "rankingDataStatus": "available"
        })

        with patch.object(
            character_controller,
            "resolve_character",
            side_effect=requests.Timeout("internal timeout"),
        ):
            response = self.client.get(
                "/api/character", query_string={"name": "테스트캐릭터"}
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["dataStatus"], "stale")
        self.assertIn("dataAsOf", body)
        self.assertEqual(body["characterName"], "테스트캐릭터")

    def test_temporary_history_failure_returns_saved_history_as_stale(self):
        self.save_snapshot("history:테스트캐릭터", {
            "characterName": "테스트캐릭터",
            "history": [{"date": "2026-10-26", "experience": 123}],
            "historyStatus": "complete"
        })

        with patch.object(
            history_controller,
            "resolve_character",
            side_effect=requests.Timeout("internal timeout"),
        ):
            response = self.client.get(
                "/api/history", query_string={"name": "테스트캐릭터"}
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["dataStatus"], "stale")
        self.assertEqual(body["history"][0]["experience"], 123)

    def test_temporary_failure_without_snapshot_returns_safe_error(self):
        with patch.object(
            character_controller,
            "resolve_character",
            side_effect=requests.Timeout("private timeout detail"),
        ):
            response = self.client.get(
                "/api/character", query_string={"name": "테스트캐릭터"}
            )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private timeout detail", response.get_data(as_text=True))
        self.assertIn("넥슨 API", response.get_data(as_text=True))

    def test_force_refresh_bypasses_character_memory_cache(self):
        with self.app.app_context():
            tracker.set_cache(
                "character:테스트캐릭터",
                {"characterName": "오래된이름", "level": 250},
                tracker.CHARACTER_CACHE_TTL,
            )

        with patch.object(
            character_controller,
            "resolve_character",
            side_effect=requests.Timeout("timeout"),
        ):
            response = self.client.get(
                "/api/character",
                query_string={"name": "테스트캐릭터", "refresh": "1"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("넥슨 API", response.get_data(as_text=True))

    def test_force_refresh_bypasses_history_memory_cache(self):
        with self.app.app_context():
            tracker.set_cache(
                "history:테스트캐릭터",
                {
                    "characterName": "테스트캐릭터",
                    "history": [{"date": "2026-10-26", "experience": 123}],
                    "historyStatus": "complete"
                },
                tracker.HISTORY_CACHE_TTL,
            )

        with patch.object(
            history_controller,
            "resolve_character",
            side_effect=requests.Timeout("timeout"),
        ):
            response = self.client.get(
                "/api/history",
                query_string={"name": "테스트캐릭터", "refresh": "1"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("넥슨 API", response.get_data(as_text=True))

    def test_empty_ranking_response_is_marked_not_ready(self):
        empty_response = Mock(status_code=200)
        with patch.object(nexon_service, "get_api_class", return_value="테스트직업"), patch.object(
            nexon_service, "get_ranking_snapshot", return_value=(None, empty_response)
        ):
            with self.app.app_context():
                result = nexon_service.get_character_rankings(
                    target_date="2026-10-27",
                    world_name="테스트월드",
                    character_class="테스트직업",
                    ocid="test-ocid"
                )

        self.assertEqual(result["rankingDataStatus"], "not_ready")


if __name__ == "__main__":
    unittest.main()
