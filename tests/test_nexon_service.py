"""Nexon service composition tests."""
import json
import unittest
from unittest.mock import Mock, patch

from tracker.services import nexon_service


class NexonServiceTests(unittest.TestCase):
    @patch("tracker.services.nexon_service.get_basic_character")
    @patch("tracker.services.nexon_service.get_ocid")
    def test_resolves_character_identity_and_basic_data(self, get_ocid, get_basic):
        id_response = Mock(status_code=200)
        basic_response = Mock(status_code=200)
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

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_job_world_and_global_ranks_are_found_in_filtered_lists(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        base_response = Mock(status_code=200)
        base_response.json.return_value = {"ranking": [{"ranking": 2278}]}
        get_ranking_snapshot.side_effect = [
            ({"ranking": 2278}, base_response),
            ({"ranking": 374}, base_response),
        ]

        def page_for(target_rank):
            response = Mock(status_code=200)
            response.json.return_value = {"ranking": [{
                "ocid": "ocid-value",
                "character_name": "밍득",
                "world_name": "크로아",
                "sub_class_name": "히어로",
                "ranking": target_rank,
            }]}
            return [{
                "ocid": "ocid-value",
                "character_name": "밍득",
                "world_name": "크로아",
                "sub_class_name": "히어로",
                "ranking": target_rank,
            }], response

        get_ranking_page.side_effect = [
            page_for(9),
            page_for(79),
        ]

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["ranking"], 2278)
        self.assertEqual(result["worldRanking"], 374)
        self.assertEqual(result["jobWorldRanking"], 9)
        self.assertEqual(result["jobRanking"], 79)
        self.assertEqual(result["rankingDataStatus"], "available")

        world_call, global_call = get_ranking_page.call_args_list
        self.assertEqual(world_call.kwargs["world_name"], "크로아")
        self.assertEqual(world_call.kwargs["character_class"], "히어로")
        self.assertEqual(global_call.kwargs["character_class"], "히어로")
        self.assertNotIn("ocid", world_call.kwargs)
        self.assertNotIn("ocid", global_call.kwargs)

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_filtered_job_rank_paginates_until_target_ocid_is_found(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        base_response = Mock(status_code=200)
        base_response.json.return_value = {"ranking": [{"ranking": 123}]}
        get_ranking_snapshot.return_value = ({"ranking": 123}, base_response)

        empty_response = Mock(status_code=200)
        empty_response.json.return_value = {"ranking": [{"ocid": "other", "ranking": 1}]}
        target_response = Mock(status_code=200)
        target_response.json.return_value = {"ranking": [{
            "ocid": "ocid-value", "ranking": 201,
        }]}

        get_ranking_page.side_effect = [
            ([{"ocid": "other", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 1}], empty_response),
            ([{"ocid": "ocid-value", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 201}], target_response),
            ([{"ocid": "ocid-value", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 201}], target_response),
        ]

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["jobWorldRanking"], 201)
        self.assertEqual(result["jobRanking"], 201)
        self.assertEqual(
            result["rankingApiDiagnostics"]["jobWorldRanking"]["pagesScanned"], 2
        )

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_equal_ordinal_job_rank_is_kept_when_found_in_filtered_list(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        base_response = Mock(status_code=200)
        base_response.json.return_value = {"ranking": [{"ranking": 123}]}
        get_ranking_snapshot.return_value = ({"ranking": 123}, base_response)
        entry = {"ocid": "ocid-value", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 123}
        page_response = Mock(status_code=200)
        page_response.json.return_value = {"ranking": [entry]}
        get_ranking_page.return_value = ([entry], page_response)

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["jobWorldRanking"], 123)
        self.assertEqual(result["jobRanking"], 123)

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_ranking_lookup_marks_three_empty_days_as_not_ready(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        empty = Mock(status_code=200)
        empty.json.return_value = {"ranking": []}
        get_ranking_snapshot.return_value = (None, empty)
        get_ranking_page.return_value = ([], empty)

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["rankingDataStatus"], "not_ready")

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_ranking_lookup_retries_previous_day_for_bad_request(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        bad = Mock(status_code=400)
        bad.json.return_value = {"error": {"name": "OPENAPI00004"}}
        good = Mock(status_code=200)
        good.json.return_value = {"ranking": [{"ranking": 10}]}

        def snapshot_side_effect(**kwargs):
            if kwargs.get("target_date") == "2026-11-08":
                return None, bad
            return {"ranking": 10}, good

        get_ranking_snapshot.side_effect = snapshot_side_effect
        get_ranking_page.side_effect = [
            ([], bad), ([], bad),
            ([{"ocid": "ocid-value", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 9}], good),
            ([{"ocid": "ocid-value", "world_name": "크로아", "sub_class_name": "히어로", "ranking": 19}], good),
        ]

        result = nexon_service.get_character_rankings(
            "2026-11-08", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["rankingDate"], "2026-11-07")
        self.assertEqual(result["jobWorldRanking"], 9)
        self.assertEqual(result["jobRanking"], 19)

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_ranking_lookup_does_not_hide_authentication_errors_with_old_dates(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        unauthorized = Mock(status_code=403)
        unauthorized.json.return_value = {"ranking": []}
        get_ranking_snapshot.return_value = (None, unauthorized)
        get_ranking_page.return_value = ([], unauthorized)

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["rankingDataStatus"], "unavailable")
        self.assertEqual(result["rankingDate"], "2026-11-07")

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_global_job_rank_name_fallback_matches_target_world(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": [{"ranking": 2278}]}
        get_ranking_snapshot.side_effect = [
            ({"ranking": 2278}, response),
            ({"ranking": 374}, response),
        ]
        global_entry = {
            "character_name": "밍득",
            "world_name": "크로아",
            "sub_class_name": "히어로",
            "ranking": 79,
        }
        world_entry = {
            "character_name": "밍득",
            "world_name": "크로아",
            "sub_class_name": "히어로",
            "ranking": 9,
        }
        get_ranking_page.side_effect = [
            ([world_entry], response),
            ([global_entry], response),
        ]

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["jobWorldRanking"], 9)
        self.assertEqual(result["jobRanking"], 79)
        self.assertEqual(result["rankingDataStatus"], "available")

    def test_api_class_uses_exact_job_name_from_character_basic(self):
        self.assertEqual(
            nexon_service.get_api_class("아크메이지(썬,콜)"),
            "아크메이지(썬,콜)",
        )
        self.assertEqual(nexon_service.get_api_class("히어로"), "히어로")
        self.assertIsNone(nexon_service.get_api_class("존재하지않는직업"))

        # Every Nexon ranking filter must use the exact character_class value,
        # not a broad class-group label such as "전사-히어로".
        with nexon_service._jobs_path().open("r", encoding="utf-8") as file:
            jobs = json.load(file)
        self.assertGreaterEqual(len(jobs), 40)
        for character_class in jobs:
            with self.subTest(character_class=character_class):
                self.assertEqual(
                    nexon_service.get_api_class(character_class),
                    character_class,
                )

    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_global_job_ranking_name_fallback_checks_world(self, get_ranking_page):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        get_ranking_page.return_value = ([{
            "character_name": "밍득",
            "world_name": "리부트",
            "sub_class_name": "아크메이지(썬,콜)",
            "ranking": 12,
        }], response)

        entry, returned_response, details = nexon_service._find_character_in_filtered_ranking(
            target_date="2026-11-07",
            world_name=None,
            api_class="아크메이지(썬,콜)",
            character_class="아크메이지(썬,콜)",
            character_name="밍득",
            ocid=None,
            target_world_name="크로아",
        )

        self.assertIsNone(entry)
        self.assertIs(returned_response, response)

    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_world_job_ranking_rejects_mismatched_world_payload(self, get_ranking_page):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        get_ranking_page.return_value = ([{
            "ocid": "target-ocid",
            "character_name": "밍득",
            "world_name": "리부트",
            "sub_class_name": "아크메이지(썬,콜)",
            "ranking": 12,
        }], response)

        entry, returned_response, details = nexon_service._find_character_in_filtered_ranking(
            target_date="2026-11-07",
            world_name="크로아",
            api_class="아크메이지(썬,콜)",
            character_class="아크메이지(썬,콜)",
            character_name="밍득",
            ocid="target-ocid",
            target_world_name="크로아",
        )

        self.assertIsNone(entry)
        self.assertIs(returned_response, response)
        self.assertTrue(details["worldFilterMismatch"])
        self.assertEqual(details["worldFilterVerification"], "mismatch")
        self.assertEqual(details["mismatchedWorld"], "리부트")

    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_world_job_ranking_rejects_payload_without_world_metadata(self, get_ranking_page):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        get_ranking_page.return_value = ([{
            "ocid": "target-ocid",
            "character_name": "밍득",
            "sub_class_name": "아크메이지(썬,콜)",
            "ranking": 79,
        }], response)

        entry, returned_response, details = nexon_service._find_character_in_filtered_ranking(
            target_date="2026-11-07",
            world_name="크로아",
            api_class="아크메이지(썬,콜)",
            character_class="아크메이지(썬,콜)",
            character_name="밍득",
            ocid="target-ocid",
            target_world_name="크로아",
        )

        self.assertIsNone(entry)
        self.assertIs(returned_response, response)
        self.assertTrue(details["filterUnverified"])
        self.assertEqual(details["worldFilterVerification"], "not_exposed")

    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_filtered_ranking_marks_missing_job_metadata_for_cross_check(self, get_ranking_page):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        get_ranking_page.return_value = ([{
            "ocid": "target-ocid",
            "character_name": "밍득",
            "world_name": "크로아",
            "ranking": 79,
        }], response)

        entry, returned_response, details = nexon_service._find_character_in_filtered_ranking(
            target_date="2026-11-07",
            world_name="크로아",
            api_class="아크메이지(썬,콜)",
            character_class="아크메이지(썬,콜)",
            character_name="밍득",
            ocid="target-ocid",
            target_world_name="크로아",
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry["ranking"], 79)
        self.assertIs(returned_response, response)
        self.assertTrue(details["filterUnverified"])
        self.assertEqual(details["filterVerification"], "not_exposed")
        self.assertTrue(details["matched"])

    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_filtered_ranking_rejects_mismatched_job_payload(self, get_ranking_page):
        response = Mock(status_code=200)
        response.json.return_value = {"ranking": []}
        get_ranking_page.return_value = ([{
            "ocid": "other",
            "character_name": "다른캐릭",
            "world_name": "크로아",
            "sub_class_name": "히어로",
            "ranking": 1,
        }], response)

        entry, returned_response, details = nexon_service._find_character_in_filtered_ranking(
            target_date="2026-11-07",
            world_name="크로아",
            api_class="아크메이지(썬,콜)",
            character_class="아크메이지(썬,콜)",
            character_name="밍득",
            ocid="target-ocid",
            target_world_name="크로아",
        )

        self.assertIsNone(entry)
        self.assertIs(returned_response, response)
        self.assertEqual(details["filterVerification"], "mismatch")
        self.assertEqual(details["mismatchedClass"], "히어로")

    @patch("tracker.services.nexon_service.get_api_class", return_value="히어로")
    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    @patch("tracker.integrations.nexon_api.get_ranking_page")
    def test_job_rank_collapsing_to_unfiltered_rank_is_rejected(
        self, get_ranking_page, get_ranking_snapshot, _get_api_class
    ):
        base_response = Mock(status_code=200)
        base_response.json.return_value = {"ranking": [{"ranking": 2278}]}
        get_ranking_snapshot.side_effect = [
            ({"ranking": 2278}, base_response),
            ({"ranking": 374}, base_response),
        ]
        page_response = Mock(status_code=200)
        page_response.json.return_value = {"ranking": []}
        get_ranking_page.side_effect = [
            ([{"ocid": "ocid-value", "world_name": "크로아", "ranking": 374}], page_response),
            ([{"ocid": "ocid-value", "world_name": "크로아", "ranking": 2278}], page_response),
        ]

        result = nexon_service.get_character_rankings(
            "2026-11-07", "크로아", "히어로", "ocid-value", "밍득"
        )

        self.assertEqual(result["ranking"], 2278)
        self.assertEqual(result["worldRanking"], 374)
        self.assertIsNone(result["jobWorldRanking"])
        self.assertIsNone(result["jobRanking"])
        self.assertTrue(
            any("종합/월드 순위와 같아" in warning for warning in result["rankingWarnings"])
        )


if __name__ == "__main__":
    unittest.main()
