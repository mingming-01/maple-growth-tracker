"""최근 캐릭터 스냅샷 재사용 테스트."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from tracker.controller.history_controller import (
    _load_recent_character_basic_snapshot,
)


class RecentCharacterBasicSnapshotTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 4, 50, tzinfo=timezone.utc)
        self.snapshot = {
            "ocid": "ocid-123",
            "characterName": "오작크로아",
            "worldName": "크로아",
            "level": 290,
            "experience": 123456,
            "experienceRate": 45.6,
        }

    @patch("tracker.controller.history_controller.load_api_snapshot")
    def test_reuses_recent_snapshot_when_ocid_and_name_match(self, load_snapshot):
        load_snapshot.return_value = (
            self.snapshot,
            self.now.isoformat(timespec="seconds"),
        )

        result = _load_recent_character_basic_snapshot(
            "오작크로아", "ocid-123", now=self.now
        )

        self.assertEqual(
            result,
            {
                "character_name": "오작크로아",
                "world_name": "크로아",
                "character_level": 290,
                "character_exp": 123456,
                "character_exp_rate": 45.6,
            },
        )
        load_snapshot.assert_called_once_with("character:오작크로아")

    @patch("tracker.controller.history_controller.load_api_snapshot")
    def test_rejects_snapshot_for_different_ocid(self, load_snapshot):
        load_snapshot.return_value = (
            self.snapshot,
            self.now.isoformat(timespec="seconds"),
        )

        result = _load_recent_character_basic_snapshot(
            "오작크로아", "different-ocid", now=self.now
        )

        self.assertIsNone(result)

    @patch("tracker.controller.history_controller.load_api_snapshot")
    def test_rejects_snapshot_for_different_character_name(self, load_snapshot):
        load_snapshot.return_value = (
            self.snapshot,
            self.now.isoformat(timespec="seconds"),
        )

        result = _load_recent_character_basic_snapshot(
            "다른캐릭터", "ocid-123", now=self.now
        )

        self.assertIsNone(result)

    @patch("tracker.controller.history_controller.load_api_snapshot")
    def test_rejects_expired_snapshot(self, load_snapshot):
        expired_at = self.now - timedelta(minutes=6)
        load_snapshot.return_value = (
            self.snapshot,
            expired_at.isoformat(timespec="seconds"),
        )

        result = _load_recent_character_basic_snapshot(
            "오작크로아", "ocid-123", now=self.now
        )

        self.assertIsNone(result)

    @patch("tracker.controller.history_controller.load_api_snapshot")
    def test_rejects_snapshot_without_timestamp(self, load_snapshot):
        load_snapshot.return_value = (self.snapshot, None)

        result = _load_recent_character_basic_snapshot(
            "오작크로아", "ocid-123", now=self.now
        )

        self.assertIsNone(result)
