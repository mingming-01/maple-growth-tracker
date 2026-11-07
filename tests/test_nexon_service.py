"""Nexon application service tests."""
import unittest
from unittest.mock import Mock, patch

from tracker.services import nexon_service


class NexonServiceTests(unittest.TestCase):
    @patch("tracker.services.nexon_service.get_basic_character")
    @patch("tracker.services.nexon_service.get_ocid")
    def test_resolves_character_identity_and_basic_data(self, get_ocid, get_basic):
        id_response = Mock()
        basic_response = Mock()
        basic = {"character_name": "밍득", "character_level": 297}
        get_ocid.return_value = ("ocid-value", id_response)
        get_basic.return_value = (basic, basic_response)

        ocid, resolved_basic, response = nexon_service.resolve_character("밍득")

        self.assertEqual(ocid, "ocid-value")
        self.assertEqual(resolved_basic, basic)
        self.assertIs(response, basic_response)
        get_ocid.assert_called_once_with("밍득")
        get_basic.assert_called_once_with("ocid-value")

    @patch("tracker.services.nexon_service.get_basic_character")
    @patch("tracker.services.nexon_service.get_ocid")
    def test_stops_when_character_id_cannot_be_resolved(self, get_ocid, get_basic):
        failed_response = Mock(status_code=404)
        get_ocid.return_value = (None, failed_response)

        ocid, basic, response = nexon_service.resolve_character("없는캐릭터")

        self.assertIsNone(ocid)
        self.assertIsNone(basic)
        self.assertIs(response, failed_response)
        get_basic.assert_not_called()

    def test_temporary_failure_classifier(self):
        self.assertTrue(nexon_service.is_temporary_nexon_failure(None))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=429)))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=503)))
        self.assertFalse(nexon_service.is_temporary_nexon_failure(Mock(status_code=404)))


    @patch("tracker.services.nexon_service.get_api_class", return_value="전사-히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_ranking_lookup_falls_back_when_today_has_no_published_data(
        self, get_ranking, _get_api_class
    ):
        empty_response = Mock(status_code=200)
        available_response = Mock(status_code=200)

        def ranking_side_effect(target_date, **kwargs):
            if target_date == "2026-11-07":
                return None, empty_response
            return {"ranking": 123}, available_response

        get_ranking.side_effect = ranking_side_effect

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value"
        )

        # The historical snapshot contains successful 200 responses for all
        # four ranking filters. Equal ordinal values alone are inconclusive,
        # so keep the job ranks rather than downgrading the snapshot to partial.
        self.assertEqual(result["rankingDataStatus"], "available")
        self.assertEqual(result["rankingDate"], "2026-11-06")
        self.assertEqual(result["ranking"], 123)
        self.assertEqual(result["jobWorldRanking"], 123)
        self.assertEqual(result["jobRanking"], 123)
        self.assertEqual(
            result["rankingApiDiagnostics"]["jobWorldRanking"]["classFilterFallback"],
            "same-rank-inconclusive",
        )
        self.assertEqual(
            result["rankingApiDiagnostics"]["jobRanking"]["classFilterFallback"],
            "same-rank-inconclusive",
        )
        self.assertEqual(get_ranking.call_count, 10)

    @patch("tracker.services.nexon_service.get_api_class", return_value="마법사-아크메이지(썬,콜)")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_job_rank_retries_with_basic_character_class_when_mapped_filter_is_ignored(
        self, get_ranking, _get_api_class
    ):
        def result(rank):
            response = Mock(status_code=200)
            response.json.return_value = {"ranking": [{"ranking": rank}]}
            return {"ranking": rank}, response

        def ranking_side_effect(target_date, world_name=None, ocid=None, character_class=None, historical=False):
            if character_class == "마법사-아크메이지(썬,콜)":
                return result(374 if world_name else 2278)
            if character_class == "아크메이지(썬,콜)":
                return result(9 if world_name else 79)
            return result(374 if world_name else 2278)

        get_ranking.side_effect = ranking_side_effect

        rankings = nexon_service.get_character_rankings(
            "2026-11-07",
            "크로아",
            "아크메이지(썬,콜)",
            "character-ocid",
        )

        self.assertEqual(rankings["worldRanking"], 374)
        self.assertEqual(rankings["ranking"], 2278)
        self.assertEqual(rankings["jobWorldRanking"], 9)
        self.assertEqual(rankings["jobRanking"], 79)
        self.assertEqual(
            rankings["rankingApiDiagnostics"]["jobWorldRanking"]["classFilterFallback"],
            "basic-character-class",
        )
        self.assertEqual(
            rankings["rankingApiDiagnostics"]["jobRanking"]["classFilterFallback"],
            "basic-character-class",
        )
        self.assertEqual(rankings["rankingDataStatus"], "available")
        self.assertEqual(get_ranking.call_count, 6)

    @patch("tracker.services.nexon_service.get_api_class", return_value="전사-히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_equal_overall_and_job_rank_is_not_misclassified_as_failed(
        self, get_ranking, _get_api_class
    ):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": [{"ranking": 123}]}
        get_ranking.return_value = ({"ranking": 123}, response)

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value"
        )

        self.assertEqual(result["rankingDataStatus"], "available")
        self.assertEqual(result["ranking"], 123)
        self.assertEqual(result["worldRanking"], 123)
        self.assertEqual(result["jobWorldRanking"], 123)
        self.assertEqual(result["jobRanking"], 123)
        self.assertEqual(
            result["rankingApiDiagnostics"]["jobWorldRanking"]["classFilterFallback"],
            "same-rank-inconclusive",
        )
        self.assertEqual(
            result["rankingApiDiagnostics"]["jobRanking"]["classFilterFallback"],
            "same-rank-inconclusive",
        )

    @patch("tracker.services.nexon_service.get_api_class", return_value="전사-히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_ranking_lookup_marks_three_empty_days_as_not_ready(
        self, get_ranking, _get_api_class
    ):
        get_ranking.return_value = (None, Mock(status_code=200))

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value"
        )

        self.assertEqual(result["rankingDataStatus"], "not_ready")
        self.assertEqual(result["rankingDate"], "2026-11-05")
        self.assertEqual(get_ranking.call_count, 12)
        self.assertTrue(result["rankingWarnings"])


    @patch("tracker.services.nexon_service.get_api_class", return_value="전사-히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_ranking_lookup_does_not_hide_authentication_errors_with_old_dates(
        self, get_ranking, _get_api_class
    ):
        unauthorized = Mock(status_code=403)
        get_ranking.return_value = (None, unauthorized)

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value"
        )

        self.assertEqual(result["rankingDataStatus"], "unavailable")
        self.assertEqual(result["rankingDate"], "2026-11-07")
        self.assertEqual(get_ranking.call_count, 4)


if __name__ == "__main__":
    unittest.main()
