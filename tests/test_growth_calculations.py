import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app as tracker
from tracker.controller import history_controller
from tracker.repositories.growth_history_store import GrowthHistoryStore
from tracker.runtime import get_runtime_state
from tracker.services.growth_history_service import GrowthHistoryService


class GrowthCalculationBehaviorTests(unittest.TestCase):
    """현재 7일·장기 기록 계산 동작을 고정하는 테스트."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.today = tracker.datetime.now(tracker.KOREA_TIMEZONE).date()
        self.store = GrowthHistoryStore(
            sqlite_path=str(Path(self.temp_dir.name) / "growth_history.sqlite3")
        )
        self.store.initialize()

        with tracker.app.app_context():
            self.state = get_runtime_state()
            self.state.growth_history_repository = self.store
            self.state.growth_history_service = GrowthHistoryService(self.store)
            self.state.snapshot_db_path = str(Path(self.temp_dir.name) / "snapshots.sqlite3")
            self.state.log_db_path = str(Path(self.temp_dir.name) / "admin_logs.sqlite3")
            self.state.log_db_backend = "sqlite"
            self.state.cache.clear()
            tracker.initialize_snapshot_db()
            tracker.initialize_log_db()

        self.client = tracker.app.test_client()

    def tearDown(self):
        with tracker.app.app_context():
            self.state.cache.clear()
        self.temp_dir.cleanup()

    def test_recent_history_excludes_level_up_experience_change(self):
        response_stub = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 281,
            "character_exp": 100,
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

    def test_archive_history_does_not_calculate_changes_across_missing_records(self):
        start_date = self.today - timedelta(days=29)
        records = [
            {
                "date": start_date.isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 1000,
                "ranking": 300,
            },
            {
                "date": (start_date + timedelta(days=1)).isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 1500,
                "ranking": 290,
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
            },
            {
                "date": (start_date + timedelta(days=4)).isoformat(),
                "recordStatus": "available",
                "level": 281,
                "experience": 100,
                "ranking": 260,
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
