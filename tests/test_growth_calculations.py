import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app as tracker
from tracker import create_app
from tracker.controller import history_controller
from tracker.domain.growth_calculations import (
    calculate_recent_history_changes,
    calculate_archive_history_changes,
    calculate_observed_experience_change,
)
from tracker.repositories.growth_history_store import GrowthHistoryStore
from tracker.runtime import get_runtime_state
from tracker.services.growth_history_service import GrowthHistoryService


class GrowthCalculationBehaviorTests(unittest.TestCase):
    """현재 7일·장기 기록 계산 동작을 고정하는 테스트."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        })
        self.temp_dir = tempfile.TemporaryDirectory()
        self.today = tracker.datetime.now(tracker.KOREA_TIMEZONE).date()
        self.store = GrowthHistoryStore(
            sqlite_path=str(Path(self.temp_dir.name) / "growth_history.sqlite3")
        )
        self.store.initialize()

        with self.app.app_context():
            self.state = get_runtime_state()
            self.state.growth_history_repository = self.store
            self.state.growth_history_service = GrowthHistoryService(self.store)
            self.state.snapshot_db_path = str(Path(self.temp_dir.name) / "snapshots.sqlite3")
            self.state.log_db_path = str(Path(self.temp_dir.name) / "admin_logs.sqlite3")
            self.state.log_db_backend = "sqlite"
            self.state.cache.clear()
            tracker.initialize_snapshot_db()
            tracker.initialize_log_db()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            self.state.cache.clear()
        self.temp_dir.cleanup()

    def test_recent_history_does_not_invent_daily_change_across_level_up(self):
        response_stub = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 281,
            "character_exp": 100,
            "character_exp_rate": "23.4567",
        }
        first_date = self.today - timedelta(days=6)

        def get_ranking(target_date, **kwargs):
            offset = (tracker.date.fromisoformat(target_date) - first_date).days
            level = 281 if offset == 6 else 280
            experience = 100 if offset == 6 else 1000 + offset * 500
            return (
                {
                    "ranking": 400 - offset * 10,
                    "character_level": level,
                    "character_exp": experience,
                },
                response_stub,
            )

        with patch.object(
            history_controller,
            "resolve_character",
            return_value=("test-ocid", basic, response_stub),
        ), patch.object(
            history_controller, "get_ranking_snapshot", side_effect=get_ranking
        ), patch.object(
            history_controller,
            "get_basic_character_snapshot",
            return_value=(basic, response_stub),
        ):
            response = self.client.get(
                "/api/history",
                query_string={"name": "테스트캐릭터", "refresh": "1"},
            )

        self.assertEqual(response.status_code, 200)
        history = response.get_json()["history"]
        self.assertEqual(len(history), 7)
        self.assertIsNone(history[6]["experienceChange"])
        self.assertTrue(history[6]["levelUp"])
        self.assertEqual(history[6]["rankingChange"], 10)
        self.assertEqual(history[6]["experienceRate"], "23.4567")
        self.assertTrue(history[6]["experienceRateChecked"])

    def test_experience_rate_reset_dates_level_up_before_ranking_level_catches_up(self):
        history = [
            {
                "date": "2026-11-17", "recordStatus": "available",
                "level": 298, "experience": 1129263590513928,
                "experienceRate": 99.226,
            },
            {
                "date": "2026-11-18", "recordStatus": "available",
                "level": 298, "experience": 1156066685461973,
                "experienceRate": 0.355,
            },
            {
                "date": "2026-11-19", "recordStatus": "available",
                "level": 299, "experience": 17096549681346,
                "experienceRate": 0.984,
            },
        ]

        calculate_recent_history_changes(history)

        self.assertTrue(history[1]["levelUp"])
        self.assertEqual(history[1]["levelUpPreviousLevel"], 298)
        self.assertEqual(history[1]["levelUpCurrentLevel"], 299)
        self.assertIsNone(history[1]["experienceChange"])
        self.assertFalse(history[2]["levelUp"])
        self.assertTrue(history[2]["levelUpCatchUp"])
        self.assertIsNone(history[2]["experienceChange"])

    def test_archive_history_uses_experience_rate_reset_for_level_up(self):
        history = [
            {
                "date": "2026-11-17", "recordStatus": "available",
                "level": 298, "experience": 1129263590513928,
                "experienceRate": 99.226,
            },
            {
                "date": "2026-11-18", "recordStatus": "available",
                "level": 298, "experience": 1156066685461973,
                "experienceRate": 0.355,
            },
            {
                "date": "2026-11-19", "recordStatus": "available",
                "level": 299, "experience": 17096549681346,
                "experienceRate": 0.984,
            },
        ]

        calculate_archive_history_changes(history)

        self.assertTrue(history[1]["levelUp"])
        self.assertEqual(history[1]["levelUpCurrentLevel"], 299)
        self.assertIsNone(history[1]["experienceChange"])
        self.assertFalse(history[2]["levelUp"])
        self.assertTrue(history[2]["levelUpCatchUp"])
        self.assertIsNone(history[2]["experienceChange"])

    def test_shared_experience_delta_preserves_large_integer_precision(self):
        previous = {
            "date": "2026-11-17", "recordStatus": "available", "level": 298,
            "experience": "9007199254740992", "experienceRate": "97.000",
        }
        current = {
            "date": "2026-11-18", "recordStatus": "available", "level": 298,
            "experience": "9007199254740993", "experienceRate": "97.001",
        }
        self.assertEqual(calculate_observed_experience_change(previous, current), 1)
        current["experience"] = float(9007199254740993)
        self.assertIsNone(calculate_observed_experience_change(previous, current))

    def test_archive_history_does_not_calculate_changes_across_missing_records(self):
        start_date = self.today - timedelta(days=29)
        records = [
            {
                "date": start_date.isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 1000,
                "ranking": 300,
                "rankingScope": "overall",
                "rankingSourceDate": start_date.isoformat(),
            },
            {
                "date": (start_date + timedelta(days=1)).isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 1500,
                "ranking": 290,
                "rankingScope": "overall",
                "rankingSourceDate": (start_date + timedelta(days=1)).isoformat(),
            },
            {
                "date": (start_date + timedelta(days=2)).isoformat(),
                "recordStatus": "not_ready",
            },
            {
                "date": (start_date + timedelta(days=3)).isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 2500,
                "ranking": 270,
                "rankingScope": "overall",
                "rankingSourceDate": (start_date + timedelta(days=3)).isoformat(),
            },
            {
                "date": (start_date + timedelta(days=4)).isoformat(),
                "recordStatus": "available",
                "level": 281,
                "experience": 100,
                "ranking": 260,
                "rankingScope": "overall",
                "rankingSourceDate": (start_date + timedelta(days=4)).isoformat(),
            },
        ]
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드", records
        )

        response = self.client.get("/api/history/archive?ocid=test-ocid&days=30")

        self.assertEqual(response.status_code, 200)
        history = response.get_json()["history"]
        self.assertEqual(history[1]["experienceChange"], 500)
        self.assertEqual(history[1]["rankingChange"], 10)
        self.assertIsNone(history[3]["experienceChange"])
        self.assertIsNone(history[3]["rankingChange"])
        self.assertTrue(history[4]["levelUp"])
        self.assertIsNone(history[4]["experienceChange"])
        self.assertEqual(history[4]["rankingChange"], 10)


if __name__ == "__main__":
    unittest.main()
