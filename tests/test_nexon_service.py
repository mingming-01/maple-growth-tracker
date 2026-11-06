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

        self.assertEqual(result["rankingDataStatus"], "available")
        self.assertEqual(result["rankingDate"], "2026-11-06")
        self.assertEqual(result["ranking"], 123)
        self.assertEqual(get_ranking.call_count, 8)

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
