"""Tests for serving usable recent history when one or more dates fail."""
import unittest
from unittest.mock import patch

from flask import Flask

from tracker.controller import history_controller


class _HistoryService:
    backend = "sqlite"
    uses_postgres = False

    def get_records(self, ocid, start_date, end_date):
        return []

    def save_records(self, ocid, character_name, world_name, records):
        return 0


class HistoryControllerPartialResponseTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(history_controller.history_bp)
        self.client = self.app.test_client()

    def test_keeps_available_days_when_another_day_is_unavailable(self):
        history = [
            {
                "date": "2026-11-19",
                "ranking": 123,
                "level": 290,
                "experience": 12345,
                "experienceRate": 12.5,
                "recordStatus": "available",
                "_fromStore": True,
            },
            {
                "date": "2026-11-20",
                "ranking": None,
                "level": None,
                "experience": None,
                "experienceRate": None,
                "recordStatus": "unavailable",
                "retryable": False,
            },
        ]
        basic = {
            "character_name": "테스트",
            "world_name": "크로아",
            "character_level": 290,
        }

        with (
            patch.object(
                history_controller,
                "get_growth_history_service",
                return_value=_HistoryService(),
            ),
            patch.object(history_controller, "get_cache", return_value=None),
            patch.object(
                history_controller, "api_request_limit_response", return_value=None
            ),
            patch.object(
                history_controller,
                "_load_recent_character_basic_snapshot",
                return_value=basic,
            ),
            patch.object(
                history_controller, "fetch_recent_history", return_value=history
            ),
            patch.object(
                history_controller, "save_api_snapshot", return_value=None
            ),
            patch.object(history_controller, "set_cache") as set_cache,
        ):
            response = self.client.get(
                "/api/history?name=%ED%85%8C%EC%8A%A4%ED%8A%B8&ocid=test-ocid&refresh=1"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["historyStatus"], "partial")
        self.assertEqual(
            [item["recordStatus"] for item in payload["history"]],
            ["available", "unavailable"],
        )
        self.assertEqual(payload["history"][0]["level"], 290)
        set_cache.assert_called_once()
        self.assertEqual(set_cache.call_args.args[2], 300)


if __name__ == "__main__":
    unittest.main()
