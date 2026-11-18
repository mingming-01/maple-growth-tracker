"""과거 성장 기록 수집 서비스 테스트."""
from datetime import date
import unittest
from unittest.mock import Mock, patch

from tracker.services import history_archive_service


class HistoryArchiveServiceTests(unittest.TestCase):
    def setUp(self):
        self.target_date = date(2026, 11, 8)
        self.today = date(2026, 11, 10)

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_uses_ranking_snapshot_without_extra_basic_request(
        self, _get_world_type, get_ranking, get_basic
    ):
        ranking_response = Mock(status_code=200)
        get_ranking.return_value = ({
            "ranking": 123,
            "character_level": 290,
            "character_exp": 98765,
            "character_exp_rate": 12.5,
        }, ranking_response)

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today
        )

        self.assertEqual(result, {
            "date": "2026-11-08",
            "ranking": 123,
            "rankingScope": "overall",
            "rankingSourceDate": "2026-11-08",
            "level": 290,
            "experience": 98765,
            "experienceRate": 12.5,
            "experienceRateChecked": True,
            "recordStatus": "available",
        })
        get_basic.assert_not_called()
        get_ranking.assert_called_once_with(
            "2026-11-08",
            world_name=None,
            ocid="ocid-1",
            world_type=0,
            historical=True,
        )

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_falls_back_to_basic_snapshot_when_ranking_is_empty(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=200))
        get_basic.return_value = ({
            "character_level": 289,
            "character_exp": 1234,
            "character_exp_rate": 8.75,
        }, Mock(status_code=200))

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today
        )

        self.assertEqual(result["recordStatus"], "available")
        self.assertEqual(result["level"], 289)
        self.assertEqual(result["experienceRate"], 8.75)
        self.assertEqual(result["rankingSourceDate"], "2026-11-08")
        self.assertEqual(result["rankingSourceDate"], "2026-11-08")
        get_basic.assert_called_once_with(
            "ocid-1", target_date="2026-11-08", historical=True
        )

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_returns_not_ready_only_when_both_apis_confirm_empty_data(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=200))
        get_basic.return_value = (None, Mock(status_code=200))

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today
        )

        self.assertEqual(result, {
            "date": "2026-11-08",
            "recordStatus": "not_ready",
        })

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_returns_none_when_api_failure_prevents_confirming_missing_data(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=503))
        get_basic.return_value = (None, Mock(status_code=200))

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today
        )

        self.assertIsNone(result)

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_ranking_api_failure_never_falls_back_to_basic_snapshot(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=503))
        get_basic.return_value = ({
            "character_level": 290,
            "character_exp": 100,
            "character_exp_rate": 2.0,
        }, Mock(status_code=200))

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today
        )

        self.assertIsNone(result)
        get_basic.assert_not_called()

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_empty_verified_ranking_clears_rank_but_preserves_saved_growth_if_basic_fails(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=200))
        get_basic.return_value = (None, Mock(status_code=503))
        saved = {
            "date": "2026-11-08",
            "recordStatus": "available",
            "level": 289,
            "experience": 98765,
            "ranking": 123,
            "rankingScope": "overall",
            "rankingSourceDate": None,
            "experienceRate": 8.75,
            "experienceRateChecked": True,
        }

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.target_date, self.today,
            saved_record=saved,
        )

        self.assertEqual(result["recordStatus"], "available")
        self.assertEqual(result["level"], 289)
        self.assertEqual(result["experience"], 98765)
        self.assertIsNone(result["ranking"])
        self.assertIsNone(result["rankingScope"])
        self.assertEqual(result["rankingSourceDate"], "2026-11-08")

    @patch("tracker.services.history_archive_service.get_basic_character_snapshot")
    @patch("tracker.services.history_archive_service.get_ranking_snapshot")
    @patch("tracker.services.history_archive_service.get_world_type", return_value=0)
    def test_uses_latest_basic_snapshot_without_date_for_today(
        self, _get_world_type, get_ranking, get_basic
    ):
        get_ranking.return_value = (None, Mock(status_code=200))
        get_basic.return_value = ({
            "character_level": 290,
            "character_exp": 100,
            "character_exp_rate": 2.0,
        }, Mock(status_code=200))

        result = history_archive_service.fetch_historical_record(
            "ocid-1", "크로아", self.today, self.today
        )

        self.assertEqual(result["recordStatus"], "available")
        self.assertEqual(result["rankingSourceDate"], "2026-11-10")
        get_basic.assert_called_once_with(
            "ocid-1", target_date=None, historical=True
        )


if __name__ == "__main__":
    unittest.main()
