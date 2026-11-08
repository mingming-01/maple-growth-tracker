"""Nexon ranking endpoint request contract tests."""
import unittest
from unittest.mock import Mock, patch

from tracker.integrations.nexon_api import get_ranking, get_ranking_page


class NexonRankingRequestTests(unittest.TestCase):
    @patch("tracker.integrations.nexon_api.request_nexon_api")
    def test_ranking_uses_class_filter_and_ocid(self, request_api):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": [{"ranking": 123, "character_name": "밍득"}]}
        request_api.return_value = response

        result, returned_response = get_ranking(
            target_date="2026-11-08",
            world_name="크로아",
            ocid="test-ocid",
            character_class="마법사-아크메이지(썬,콜)",
        )

        self.assertEqual(result["ranking"], 123)
        self.assertIs(returned_response, response)
        endpoint, params = request_api.call_args.args[:2]
        self.assertEqual(endpoint, "ranking/overall")
        self.assertEqual(params["date"], "2026-11-08")
        self.assertEqual(params["world_type"], 0)
        self.assertEqual(params["world_name"], "크로아")
        self.assertEqual(params["ocid"], "test-ocid")
        self.assertEqual(params["class"], "마법사-아크메이지(썬,콜)")
        self.assertNotIn("character_class", params)

    @patch("tracker.integrations.nexon_api.request_nexon_api")
    def test_ranking_page_uses_class_and_reboot_world_type(self, request_api):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": [{"ranking": 1}]}
        request_api.return_value = response

        rows, returned_response = get_ranking_page(
            target_date="2026-11-08",
            world_name="에오스",
            character_class="프렌즈 월드-키네시스",
            world_type=1,
            page=2,
        )

        self.assertEqual(rows[0]["ranking"], 1)
        self.assertIs(returned_response, response)
        _, params = request_api.call_args.args[:2]
        self.assertEqual(params["world_name"], "에오스")
        self.assertEqual(params["world_type"], 1)
        self.assertEqual(params["class"], "프렌즈 월드-키네시스")
        self.assertEqual(params["page"], 2)
        self.assertNotIn("ocid", params)

    @patch("tracker.integrations.nexon_api.request_nexon_api")
    def test_ranking_returns_none_for_empty_ocid_result(self, request_api):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        request_api.return_value = response

        result, returned_response = get_ranking("2026-11-08", ocid="test-ocid")

        self.assertIsNone(result)
        self.assertIs(returned_response, response)


if __name__ == "__main__":
    unittest.main()
