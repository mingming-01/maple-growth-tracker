import unittest
from unittest.mock import patch

from tracker.services.character_detail_service import (
    get_character_detail_section,
    _normalize_source,
    SECTION_SOURCES,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class CharacterDetailServiceTests(unittest.TestCase):
    def test_stat_source_extracts_actual_combat_power(self):
        spec = SECTION_SOURCES["stats"][0]
        result = _normalize_source(
            {
                "final_stat": [
                    {"stat_name": "STR", "stat_value": "12000"},
                    {"stat_name": "전투력", "stat_value": "123456789"},
                ]
            },
            spec,
        )
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["combatPower"], "123456789")
        self.assertEqual(result["data"]["final_stat"][0]["stat_name"], "STR")

    def test_hyper_stat_presets_keep_active_number_and_each_configuration(self):
        spec = SECTION_SOURCES["stats"][1]
        result = _normalize_source(
            {
                "use_preset_no": "2",
                "hyper_stat_preset_1": [{"stat_type": "크리티컬 데미지", "stat_level": 5}],
                "hyper_stat_preset_2": [{"stat_type": "보스 데미지", "stat_level": 10}],
                "hyper_stat_preset_3": [],
            },
            spec,
        )
        self.assertEqual(result["activePresetNo"], 2)
        self.assertEqual([item["number"] for item in result["presets"]], [1, 2])
        self.assertEqual(
            result["presets"][1]["data"]["hyper_stat"][0]["stat_level"],
            10,
        )

    def test_union_raider_merges_separate_raider_and_block_preset_payloads(self):
        spec = SECTION_SOURCES["union"][1]
        result = _normalize_source(
            {
                "union_raider_preset_no": 3,
                "union_raider_preset_3": {"union_raider_stat": ["보스 데미지 증가"]},
                "union_block_preset_3": {"union_block": [{"block_type": "전사"}]},
                "union_occupied_stat": ["공격력 증가"],
            },
            spec,
        )
        self.assertEqual(result["activePresetNo"], 3)
        self.assertEqual(len(result["presets"]), 1)
        self.assertIn("union_raider", result["presets"][0]["data"])
        self.assertIn("union_block", result["presets"][0]["data"])
        self.assertIn("union_occupied_stat", result["data"])

    def test_section_returns_partial_when_one_detail_api_fails(self):
        payloads = {
            "character/stat": FakeResponse(200, {"final_stat": [{"stat_name": "전투력", "stat_value": "100"}]}),
            "character/hyper-stat": FakeResponse(403, {}),
            "character/ability": FakeResponse(200, {"ability_info": [{"ability_value": "보스 데미지"}]}),
        }

        def fake_request(endpoint, params):
            self.assertEqual(params.get("ocid"), "sample-ocid")
            return payloads.get(endpoint, FakeResponse(200, {}))

        with patch(
            "tracker.services.character_detail_service.request_nexon_api",
            side_effect=fake_request,
        ):
            result = get_character_detail_section("sample-ocid", "stats")

        self.assertEqual(result["status"], "partial")
        statuses = {source["id"]: source["status"] for source in result["sources"]}
        self.assertEqual(statuses["stat"], "available")
        self.assertEqual(statuses["hyperStat"], "unavailable")
        self.assertEqual(statuses["ability"], "available")

    def test_preset_classifier_uses_option_signals_and_keeps_ambiguous_unknown(self):
        from tracker.services.character_detail_service import _classify_preset
        self.assertEqual(_classify_preset("ability", {"ability_value": "보스 몬스터 공격 시 데미지 +20%"})["purpose"], "boss")
        self.assertEqual(_classify_preset("ability", {"ability_value": "메소 획득량 +20%"})["purpose"], "hunting")
        self.assertEqual(_classify_preset("hyperStat", {"stat_type": "STR"})["purpose"], "unknown")

    def test_skills_section_requests_sixth_job_skills_and_hexa_data(self):
        payloads = {
            "character/skill": FakeResponse(200, {"character_skill_grade": "6", "character_skill": [{"skill_name": "테스트 6차", "skill_level": 1}]}),
            "character/hexamatrix": FakeResponse(200, {"character_hexa_core_equipment": [{"hexa_core_name": "테스트 코어", "hexa_core_level": 10}]}),
            "character/hexamatrix-stat": FakeResponse(200, {"character_hexa_stat_core": [{"slot_id": "1"}]}),
        }
        def fake_request(endpoint, params):
            self.assertEqual(params.get("ocid"), "sample-ocid")
            if endpoint == "character/skill":
                self.assertEqual(params.get("character_skill_grade"), "6")
            return payloads[endpoint]
        with patch("tracker.services.character_detail_service.request_nexon_api", side_effect=fake_request):
            result = get_character_detail_section("sample-ocid", "skills")
        self.assertEqual(result["status"], "available")
        self.assertEqual([source["id"] for source in result["sources"]], ["skill6", "hexaMatrix", "hexaStat"])

    def test_item_equipment_preset_payload_is_normalized_to_slot_key(self):
        spec = SECTION_SOURCES["equipment"][0]
        result = _normalize_source({
            "preset_no": 2,
            "item_equipment_preset_1": [{"item_equipment_slot": "모자", "item_name": "테스트 모자"}],
            "item_equipment_preset_2": [{"item_equipment_slot": "무기", "item_name": "테스트 무기"}],
        }, spec)
        self.assertEqual(result["activePresetNo"], 2)
        self.assertEqual(result["presets"][0]["data"]["item_equipment"][0]["item_name"], "테스트 모자")
        self.assertEqual(result["presets"][1]["data"]["item_equipment"][0]["item_name"], "테스트 무기")

    def test_link_preset_combines_equipped_and_owned_link_skills(self):
        spec = SECTION_SOURCES["stats"][4]
        result = _normalize_source({
            "use_preset_no": 1,
            "character_link_skill_preset_1": [{"skill_name": "소울 컨트랙트"}],
            "character_owned_link_skill_preset_1": {"skill_name": "데몬스 퓨리"},
        }, spec)
        preset = result["presets"][0]
        self.assertEqual(preset["data"]["character_link_skill"][0]["skill_name"], "소울 컨트랙트")
        self.assertEqual(preset["data"]["character_owned_link_skill"]["skill_name"], "데몬스 퓨리")
        self.assertEqual(preset["bossScore"], 6)

    def test_profile_recommendation_combines_equipment_link_and_hyper_signals(self):
        from tracker.services.character_detail_service import recommend_preset_profiles
        sources = [
            {"id": "itemEquipment", "activePresetNo": 1, "presets": [
                {"number": 1, "bossScore": 0, "huntingScore": 4},
                {"number": 2, "bossScore": 4, "huntingScore": 0},
            ]},
            {"id": "linkSkill", "activePresetNo": 1, "presets": [
                {"number": 1, "bossScore": 0, "huntingScore": 3},
                {"number": 2, "bossScore": 6, "huntingScore": 0},
            ]},
            {"id": "hyperStat", "activePresetNo": 1, "presets": [
                {"number": 1, "bossScore": 0, "huntingScore": 4},
                {"number": 2, "bossScore": 5, "huntingScore": 0},
            ]},
        ]
        result = recommend_preset_profiles(sources)
        self.assertEqual(result["boss"]["presetNumbers"]["equipment"], 2)
        self.assertEqual(result["boss"]["presetNumbers"]["link"], 2)
        self.assertEqual(result["boss"]["presetNumbers"]["hyperStat"], 2)
        self.assertEqual(result["hunting"]["presetNumbers"]["equipment"], 1)

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError):
            get_character_detail_section("sample-ocid", "unknown")


if __name__ == "__main__":
    unittest.main()
