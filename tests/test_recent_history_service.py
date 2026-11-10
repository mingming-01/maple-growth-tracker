"""최근 성장 기록 수집 서비스 테스트."""
from datetime import date, timedelta
import unittest
from unittest.mock import Mock

from tracker.services.recent_history_service import fetch_recent_history


class RecentHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 10)
        self.yesterday = self.today - timedelta(days=1)
        self.response = Mock(status_code=200)
        self.ranking = Mock(return_value=({
            "ranking": 123,
            "character_level": 290,
            "character_exp": 12345,
            "character_exp_rate": 12.5,
        }, self.response))
        self.basic_lookup = Mock(return_value=(None, self.response))
        self.world_type = Mock(return_value=0)
        self.temporary_failure = Mock(return_value=False)
        self.metric = Mock()

    def collect(self, dates, *, basic=None, stored=None):
        return fetch_recent_history(
            dates,
            basic=basic or {
                "character_name": "테스트",
                "world_name": "크로아",
                "character_level": 290,
                "character_exp": 12345,
            },
            ocid="test-ocid",
            world_name="크로아",
            stored_recent=stored or {},
            today=self.today,
            get_ranking_snapshot=self.ranking,
            get_basic_character_snapshot=self.basic_lookup,
            get_world_type=self.world_type,
            is_temporary_nexon_failure=self.temporary_failure,
            increment_metric=self.metric,
            max_workers=1,
        )

    def test_reuses_fully_checked_saved_record_without_api_calls(self):
        saved = {
            "2026-11-09": {
                "ranking": 456,
                "level": 289,
                "experience": 9876,
                "experienceRate": 11.2,
                "experienceRateChecked": True,
                "recordStatus": "available",
            }
        }

        result = self.collect([self.yesterday], stored=saved)

        self.assertEqual(result[0]["ranking"], 456)
        self.assertTrue(result[0]["_fromStore"])
        self.ranking.assert_not_called()
        self.basic_lookup.assert_not_called()

    def test_fetches_ranking_first_and_returns_available_record(self):
        result = self.collect([self.yesterday])

        self.assertEqual(result[0]["recordStatus"], "available")
        self.assertEqual(result[0]["experienceRate"], 12.5)
        self.ranking.assert_called_once_with(
            target_date="2026-11-09",
            world_name="크로아",
            ocid="test-ocid",
            world_type=0,
        )
        self.basic_lookup.assert_not_called()

    def test_uses_basic_snapshot_when_ranking_is_empty(self):
        self.ranking.return_value = (None, self.response)
        self.basic_lookup.return_value = ({
            "character_level": 288,
            "character_exp": 6543,
            "character_exp_rate": 8.5,
        }, self.response)

        result = self.collect([self.yesterday])

        self.assertEqual(result[0]["recordStatus"], "available")
        self.assertEqual(result[0]["level"], 288)
        self.assertEqual(result[0]["experienceRate"], 8.5)
        self.basic_lookup.assert_called_once_with(
            "test-ocid", target_date="2026-11-09", historical=True
        )

    def test_does_not_call_basic_api_after_temporary_ranking_failure(self):
        failed_response = Mock(status_code=503)
        self.ranking.return_value = (None, failed_response)
        self.temporary_failure.return_value = True

        result = self.collect([self.yesterday])

        self.assertEqual(result[0]["recordStatus"], "unavailable")
        self.assertTrue(result[0]["retryable"])
        self.basic_lookup.assert_not_called()

    def test_reuses_today_ranking_from_character_snapshot(self):
        basic = {
            "character_name": "테스트",
            "world_name": "크로아",
            "character_level": 290,
            "character_exp": 12345,
            "ranking": 99,
            "ranking_data_status": "available",
            "character_exp_rate": 7.5,
        }

        result = self.collect([self.today], basic=basic)

        self.assertEqual(result[0]["ranking"], 99)
        self.assertEqual(result[0]["recordStatus"], "available")
        self.ranking.assert_not_called()
        self.metric.assert_called_once_with("history.current_ranking_reused")


if __name__ == "__main__":
    unittest.main()
