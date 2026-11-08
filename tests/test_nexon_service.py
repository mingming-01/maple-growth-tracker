"""Nexon service composition tests."""
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tracker.services import nexon_service


def response_for(entry, status=200):
    response = Mock(status_code=status)
    response.json.return_value = {"ranking": [entry] if entry else []}
    return response


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

    def test_temporary_failure_classifier(self):
        self.assertTrue(nexon_service.is_temporary_nexon_failure(None))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=429)))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=503)))
        self.assertFalse(nexon_service.is_temporary_nexon_failure(Mock(status_code=404)))

    def test_world_type_uses_reboot_type_for_eos_and_helios(self):
        self.assertEqual(nexon_service.get_world_type("에오스"), 1)
        self.assertEqual(nexon_service.get_world_type("헬리오스"), 1)
        self.assertEqual(nexon_service.get_world_type("크로아"), 0)

    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_stops_historical_date_retry_after_temporary_failure(self, get_snapshot):
        overall = {
            "ranking": 200,
            "class_name": "마법사",
            "sub_class_name": "아크메이지(썬,콜)",
            "world_name": "크로아",
        }

        def snapshot(**kwargs):
            if not kwargs.get("character_class") and not kwargs.get("world_name"):
                return overall, response_for(overall)
            return None, response_for(None, status=429)

        get_snapshot.side_effect = snapshot
        result = nexon_service.get_character_rankings(
            "2026-11-08", "크로아", "아크메이지(썬,콜)", "ocid-value"
        )

        self.assertEqual(get_snapshot.call_count, 4)
        self.assertEqual(result["rankingDate"], "2026-11-08")
        self.assertEqual(result["ranking"], 200)
        self.assertEqual(result["rankingDataStatus"], "partial")

    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_uses_ranking_response_job_metadata_and_direct_ocid_filters(self, get_snapshot):
        overall = {
            "ranking": 200,
            "class_name": "마법사",
            "sub_class_name": "아크메이지(썬,콜)",
            "world_name": "크로아",
        }
        world = {**overall, "ranking": 100}
        job_world = {**overall, "ranking": 8}
        job = {**overall, "ranking": 20}

        def snapshot(**kwargs):
            if kwargs.get("character_class") and kwargs.get("world_name"):
                entry = job_world
            elif kwargs.get("character_class"):
                entry = job
            elif kwargs.get("world_name"):
                entry = world
            else:
                entry = overall
            return entry, response_for(entry)

        get_snapshot.side_effect = snapshot
        result = nexon_service.get_character_rankings(
            "2026-11-08", "크로아", "아크메이지(썬,콜)", "ocid-value"
        )

        self.assertEqual(result["ranking"], 200)
        self.assertEqual(result["worldRanking"], 100)
        self.assertEqual(result["jobWorldRanking"], 8)
        self.assertEqual(result["jobRanking"], 20)
        self.assertEqual(result["rankingDataStatus"], "available")
        self.assertEqual(get_snapshot.call_count, 4)
        filtered_calls = [
            call.kwargs for call in get_snapshot.call_args_list
            if call.kwargs.get("character_class")
        ]
        self.assertEqual(len(filtered_calls), 2)
        self.assertEqual(
            {call["character_class"] for call in filtered_calls},
            {"마법사-아크메이지(썬,콜)"},
        )
        self.assertTrue(all(call["ocid"] == "ocid-value" for call in filtered_calls))

    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_uses_world_type_one_for_renamed_reboot_world(self, get_snapshot):
        overall = {
            "ranking": 200,
            "class_name": "프렌즈 월드",
            "sub_class_name": "키네시스",
            "world_name": "에오스",
        }

        def snapshot(**kwargs):
            entry = dict(overall)
            if kwargs.get("character_class") and kwargs.get("world_name"):
                entry["ranking"] = 8
            elif kwargs.get("character_class"):
                entry["ranking"] = 20
            elif kwargs.get("world_name"):
                entry["ranking"] = 100
            return entry, response_for(entry)

        get_snapshot.side_effect = snapshot
        result = nexon_service.get_character_rankings(
            "2026-11-08", "에오스", "키네시스", "ocid-value"
        )

        self.assertEqual(result["rankingDataStatus"], "available")
        self.assertTrue(all(
            call.kwargs["world_type"] == 1 for call in get_snapshot.call_args_list
        ))

    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_rejects_filtered_rank_with_wrong_job_metadata(self, get_snapshot):
        overall = {
            "ranking": 200,
            "class_name": "마법사",
            "sub_class_name": "아크메이지(썬,콜)",
            "world_name": "크로아",
        }

        def snapshot(**kwargs):
            entry = dict(overall)
            if kwargs.get("character_class"):
                entry.update(class_name="전사", sub_class_name="히어로", ranking=1)
            elif kwargs.get("world_name"):
                entry["ranking"] = 100
            return entry, response_for(entry)

        get_snapshot.side_effect = snapshot
        result = nexon_service.get_character_rankings(
            "2026-11-08", "크로아", "아크메이지(썬,콜)", "ocid-value"
        )

        self.assertIsNone(result["jobWorldRanking"])
        self.assertIsNone(result["jobRanking"])
        self.assertTrue(any("직업과 달라" in warning for warning in result["rankingWarnings"]))

    @patch("tracker.services.nexon_service.get_ranking_snapshot")
    def test_rejects_impossible_rank_relationship(self, get_snapshot):
        overall = {
            "ranking": 10,
            "class_name": "마법사",
            "sub_class_name": "아크메이지(썬,콜)",
            "world_name": "크로아",
        }

        def snapshot(**kwargs):
            entry = dict(overall)
            if kwargs.get("character_class"):
                entry["ranking"] = 11
            elif kwargs.get("world_name"):
                entry["ranking"] = 5
            return entry, response_for(entry)

        get_snapshot.side_effect = snapshot
        result = nexon_service.get_character_rankings(
            "2026-11-08", "크로아", "아크메이지(썬,콜)", "ocid-value"
        )

        self.assertIsNone(result["jobRanking"])
        self.assertTrue(any("순위 관계" in warning for warning in result["rankingWarnings"]))

    def test_api_class_mapping_is_fallback_in_expected_format(self):
        self.assertEqual(nexon_service.get_api_class("히어로"), "전사-히어로")
        self.assertEqual(
            nexon_service.get_api_class("아크메이지(썬,콜)"),
            "마법사-아크메이지(썬,콜)",
        )
        self.assertIsNone(nexon_service.get_api_class("존재하지않는직업"))

    def test_sanitized_live_response_fixture_passes_filter_validation(self):
        fixture_path = Path(__file__).parent / "fixtures" / "nexon_ranking_filtered_sample.json"
        with fixture_path.open(encoding="utf-8") as fixture_file:
            entry = json.load(fixture_file)["ranking"][0]
        self.assertEqual(
            nexon_service._validate_filtered_entry(
                entry, "프렌즈 월드-키네시스", "루나"
            ),
            (True, "verified"),
        )


if __name__ == "__main__":
    unittest.main()
