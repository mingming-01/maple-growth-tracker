"""Nexon ranking endpoint request contract tests."""
import unittest
from unittest.mock import Mock, patch

from tracker.integrations.nexon_api import get_ranking, get_ranking_page


class NexonRankingRequestTests(unittest.TestCase):
    @patch("tracker.integrations.nexon_api.request_nexon_api")
    def test_ranking_uses_character_class_parameter(self, request_api):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": [{"ranking": 123, "character_name": "밍득"}]}
        request_api.return_value = response

        result, returned_response = get_ranking(
            target_date="2026-11-06",
            world_name="크로아",
            ocid="test-ocid",
            character_class="전사-히어로",
        )

        self.assertEqual(result["ranking"], 123)
        self.assertIs(returned_response, response)
        request_api.assert_called_once()
        endpoint, params = request_api.call_args.args[:2]
        self.assertEqual(endpoint, "ranking/overall")
        self.assertEqual(params["date"], "2026-11-06")
        self.assertEqual(params["world_type"], 0)
        self.assertEqual(params["page"], 1)
        self.assertEqual(params["world_name"], "크로아")
        self.assertEqual(params["ocid"], "test-ocid")
        self.assertEqual(params["character_class"], "전사-히어로")
        self.assertNotIn("class", params)

    @patch("tracker.integrations.nexon_api.request_nexon_api")
    def test_filtered_ranking_page_omits_ocid_and_returns_full_list(self, request_api):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ranking": [
                {"ocid": "one", "ranking": 1},
                {"ocid": "target", "ranking": 2},
            ]
        }
        request_api.return_value = response

        rows, returned_response = get_ranking_page(
            target_date="2026-11-06",
            world_name="크로아",
            character_class="전사-히어로",
            page=1,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["ocid"], "target")
        self.assertIs(returned_response, response)
        endpoint, params = request_api.call_args.args[:2]
        self.assertEqual(endpoint, "ranking/overall")
        self.assertEqual(params["world_name"], "크로아")
        self.assertEqual(params["character_class"], "전사-히어로")
        self.assertEqual(params["page"], 1)
        self.assertNotIn("ocid", params)


if __name__ == "__main__":
    unittest.main()
