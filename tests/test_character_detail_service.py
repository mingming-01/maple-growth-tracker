"""Character detail service tests (Phase 1: stats sources reduced)."""
import unittest
from unittest.mock import patch

from tracker.services.character_detail_service import (
    SECTION_SOURCES,
    get_character_detail_section,
    _normalize_source,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class CharacterDetailServiceTests(unittest.TestCase):
    def test_stats_section_only_has_three_sources(self):
        ids = [spec["id"] for spec in SECTION_SOURCES["stats"]]
        self.assertEqual(ids, ["stat", "hyperStat", "ability"])

    def test_stats_section_requests_only_stat_hyper_and_ability(self):
        called = []

        def fake_request(endpoint, params):
            called.append(endpoint)
            return FakeResponse(200, {"final_stat": [{"stat_name": "전투력", "stat_value": "1"}]})

        with patch(
            "tracker.services.character_detail_service.request_nexon_api",
            side_effect=fake_request,
        ):
            result = get_character_detail_section(
                "unique-stats-ocid-force-refresh", "stats", force_refresh=True
            )

        self.assertEqual(
            sorted(called),
            sorted(["character/stat", "character/hyper-stat", "character/ability"]),
        )
        self.assertEqual(len(result["sources"]), 3)
        self.assertEqual(
            {source["id"] for source in result["sources"]},
            {"stat", "hyperStat", "ability"},
        )

    def test_section_returns_partial_when_one_detail_api_fails(self):
        def fake_request(endpoint, params):
            if endpoint == "character/hyper-stat":
                return FakeResponse(500, {})
            return FakeResponse(200, {"final_stat": [{"stat_name": "전투력", "stat_value": "10"}]})

        with patch(
            "tracker.services.character_detail_service.request_nexon_api",
            side_effect=fake_request,
        ):
            result = get_character_detail_section("sample-ocid", "stats", force_refresh=True)

        self.assertEqual(result["status"], "partial")
        statuses = {source["id"]: source["status"] for source in result["sources"]}
        self.assertEqual(statuses["stat"], "available")
        self.assertEqual(statuses["hyperStat"], "unavailable")

    def test_stat_source_extracts_actual_combat_power(self):
        spec = SECTION_SOURCES["stats"][0]
        result = _normalize_source(
            {"final_stat": [{"stat_name": "전투력", "stat_value": "123456"}]},
            spec,
        )
        self.assertEqual(result["combatPower"], "123456")

    def test_equipment_section_still_includes_item_equipment(self):
        ids = [spec["id"] for spec in SECTION_SOURCES["equipment"]]
        self.assertIn("itemEquipment", ids)

    def test_link_and_union_sections_keep_dedicated_sources(self):
        self.assertEqual([s["id"] for s in SECTION_SOURCES["link"]], ["linkSkill"])
        self.assertIn("unionStateStat", [s["id"] for s in SECTION_SOURCES["union"]])

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError):
            get_character_detail_section("sample-ocid", "unknown")


if __name__ == "__main__":
    unittest.main()
