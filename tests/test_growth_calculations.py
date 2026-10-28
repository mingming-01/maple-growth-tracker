import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app as tracker
from tracker.controller import history_controller
from growth_history_store import GrowthHistoryStore


class GrowthCalculationBehaviorTests(unittest.TestCase):
    """현재 7일·장기 기록 계산 동작을 고정하는 테스트."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.today = tracker.datetime.now(tracker.KOREA_TIMEZONE).date()
        self.store = GrowthHistoryStore(
            sqlite_path=str(Path(self.temp_dir.name) / "growth_history.sqlite3")
        )
        self.store.initialize()

        self.store_patch = patch.object(tracker, "growth_history_store", self.store)
        self.controller_store_patch = patch.object(history_controller, "growth_history_store", self.store)
        self.snapshot_patch = patch.object(
            tracker,
            "SNAPSHOT_DB_PATH",
            str(Path(self.temp_dir.name) / "snapshots.sqlite3"),
        )
        self.log_patch = patch.object(tracker, "log_action")
        self.store_patch.start()
        self.controller_store_patch.start()
        self.snapshot_patch.start()
        self.log_patch.start()
        tracker.initialize_snapshot_db()
        tracker.CACHE.clear()
        self.client = tracker.app.test_client()

    def tearDown(self):
        tracker.CACHE.clear()
        self.log_patch.stop()
        self.snapshot_patch.stop()
        self.controller_store_patch.stop()
        self.store_patch.stop()
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
            history_controller, "get_ocid", return_value=("test-ocid", response_stub)
        ), patch.object(
            history_controller, "get_basic_character", return_value=(basic, response_stub)
        ), patch.object(
            history_controller, "get_ranking", side_effect=get_ranking
        ):
            response = self.client.get(
                "/api/history?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0&refresh=1"
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
