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

    def test_union_state_stat_presets_use_modern_schema_and_match_active_effects(self):
        spec = SECTION_SOURCES["union"][1]
        result = _normalize_source(
            {
                "use_preset_no": 1,  # 구형 공격대 전투 지도 번호이므로 새 스탯 프리셋 번호로 사용하지 않는다.
                "union_max_point": 9000,
                "union_state_stat": ["보스 몬스터 공격 시 데미지 20% 증가", "크리티컬 데미지 5% 증가"],
                "union_state_stat_preset": [
                    {"preset_no": 1, "union_state_stat": ["경험치 획득량 10% 증가"]},
                    {"preset_no": 2, "union_state_stat": ["크리티컬 데미지 5% 증가", "보스 몬스터 공격 시 데미지 20% 증가"]},
                ],
                "union_block": [{"block_type": "전사"}],  # 구형 테트리스 데이터는 새 UI 데이터에서 제외한다.
                "union_inner_stat": [{"stat_field_id": "0", "stat_field_effect": "공격력 증가"}],
            },
            spec,
        )
        self.assertEqual(result["activePresetNo"], 2)
        self.assertEqual([item["number"] for item in result["presets"]], [1, 2])
        self.assertEqual(
            result["presets"][0]["data"]["union_state_stat"],
            ["경험치 획득량 10% 증가"],
        )
        self.assertEqual(result["data"]["union_max_point"], 9000)
        self.assertNotIn("union_block", result["data"])
        self.assertNotIn("union_inner_stat", result["data"])
        # 유니온 프리셋은 사용자가 번호로 직접 구분하므로 자동 목적 판정을 하지 않는다.
        self.assertEqual(result["presets"][0]["purpose"], "unknown")
        self.assertEqual(result["presets"][1]["purpose"], "unknown")
        self.assertEqual(result["presets"][0]["bossScore"], 0)
        self.assertEqual(result["presets"][0]["huntingScore"], 0)

    def test_union_state_stat_keeps_unknown_active_preset_unconfirmed(self):
        spec = SECTION_SOURCES["union"][1]
        result = _normalize_source(
            {
                "use_preset_no": 3,
                "union_max_point": 6000,
                "union_state_stat": ["보스 데미지 10% 증가"],
                "union_state_stat_preset": [
                    {"preset_no": 1, "union_state_stat": ["경험치 획득량 5% 증가"]},
                    {"preset_no": 2, "union_state_stat": ["메소 획득량 5% 증가"]},
                ],
            },
            spec,
        )
        self.assertIsNone(result["activePresetNo"])

    def test_union_state_stat_does_not_guess_between_identical_preset_effects(self):
        spec = SECTION_SOURCES["union"][1]
        result = _normalize_source(
            {
                "union_state_stat": ["보스 데미지 10% 증가"],
                "union_state_stat_preset": [
                    {"preset_no": 1, "union_state_stat": ["보스 데미지 10% 증가"]},
                    {"preset_no": 2, "union_state_stat": ["보스 데미지 10% 증가"]},
                ],
            },
            spec,
        )
        self.assertIsNone(result["activePresetNo"])

    def test_union_state_stat_falls_back_to_current_configuration_without_presets(self):
        spec = SECTION_SOURCES["union"][1]
        result = _normalize_source(
            {"union_state_stat": ["경험치 획득량 10% 증가"], "union_state_stat_preset": []},
            spec,
        )
        self.assertEqual(result["activePresetNo"], 0)
        self.assertEqual(result["presets"][0]["number"], 0)
        self.assertTrue(result["presets"][0]["currentOnly"])
        self.assertEqual(
            result["presets"][0]["data"]["union_state_stat"],
            ["경험치 획득량 10% 증가"],
        )

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

    def test_ability_presets_normalize_nested_ability_info_and_grade(self):
        spec = SECTION_SOURCES["stats"][2]
        result = _normalize_source(
            {
                "ability_grade": "레전드리",
                "preset_no": 2,
                "ability_info": [{"ability_value": "보스 데미지 +20%"}],
                "ability_preset_1": {
                    "ability_preset_grade": "유니크",
                    "ability_info": [{"ability_no": "1", "ability_grade": "유니크", "ability_value": "메소 획득량 +10%"}],
                },
                "ability_preset_2": {
                    "ability_preset_grade": "레전드리",
                    "ability_info": [{"ability_no": "1", "ability_grade": "레전드리", "ability_value": "재사용 대기시간 미적용 +7.5%"}],
                },
            },
            spec,
        )
        self.assertEqual(result["activePresetNo"], 2)
        self.assertEqual(result["presets"][0]["data"]["ability_grade"], "유니크")
        self.assertEqual(
            result["presets"][0]["data"]["ability_info"][0]["ability_value"],
            "메소 획득량 +10%",
        )
        self.assertEqual(
            result["presets"][1]["data"]["ability_info"][0]["ability_value"],
            "재사용 대기시간 미적용 +7.5%",
        )

    def test_hyper_stat_classifier_uses_invested_levels_for_hunting_and_boss(self):
        from tracker.services.character_detail_service import _classify_preset

        hunting = _classify_preset("hyperStat", {"hyper_stat": [
            {"stat_type": "일반 몬스터 데미지", "stat_level": 10},
            {"stat_type": "경험치 획득량", "stat_level": 10},
            {"stat_type": "크리티컬 데미지", "stat_level": 2},
        ]})
        boss = _classify_preset("hyperStat", {"hyper_stat": [
            {"stat_type": "보스 데미지", "stat_level": 10},
            {"stat_type": "몬스터 방어율 무시", "stat_level": 10},
            {"stat_type": "데미지", "stat_level": 5},
        ]})
        generic = _classify_preset("hyperStat", {"hyper_stat": [
            {"stat_type": "데미지", "stat_level": 10},
            {"stat_type": "공격력", "stat_level": 10},
        ]})
        self.assertEqual(hunting["purpose"], "hunting")
        self.assertEqual(boss["purpose"], "boss")
        self.assertEqual(generic["purpose"], "unknown")
        self.assertIn("일반 몬스터 데미지 Lv.10", hunting["signals"])

    def test_union_stat_presets_are_not_classified_as_boss_or_hunting(self):
        from tracker.services.character_detail_service import _classify_preset

        result = _classify_preset(
            "unionStateStat",
            {"union_state_stat": ["보스 몬스터 공격 시 데미지 20% 증가"]},
        )
        self.assertEqual(result["purpose"], "unknown")
        self.assertEqual(result["bossScore"], 0)
        self.assertEqual(result["huntingScore"], 0)

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

    def test_union_section_fetches_state_presets_artifact_crystals_and_champions(self):
        payloads = {
            "user/union": FakeResponse(200, {"union_level": 9000, "union_grade": "그랜드 마스터 유니온"}),
            "user/union-raider": FakeResponse(200, {
                "union_max_point": 9000,
                "union_state_stat": ["경험치 획득량 10% 증가"],
                "union_state_stat_preset": [
                    {"preset_no": 1, "union_state_stat": ["경험치 획득량 10% 증가"]},
                    {"preset_no": 2, "union_state_stat": ["보스 몬스터 공격 시 데미지 20% 증가"]},
                ],
                "union_block": [],
            }),
            "user/union-artifact": FakeResponse(200, {
                "union_artifact_effect": [{"name": "올스탯 증가", "level": 10}],
                "union_artifact_crystal": [{
                    "name": "주황버섯", "level": 5, "validity_flag": "0", "is_expired": False,
                    "crystal_option_name_1": "버프 지속시간 증가",
                    "crystal_option_name_2": "크리티컬 데미지 증가",
                    "crystal_option_name_3": "보스 몬스터 공격 시 데미지 증가",
                }],
                "union_artifact_remain_ap": 20,
            }),
            "user/union-champion": FakeResponse(200, {
                "union_champion": [{
                    "champion_name": "테스트캐릭터", "champion_slot": 1,
                    "champion_grade": "SSS", "champion_class": "아크메이지(불,독)",
                    "champion_badge_info": [{"stat": "보스 몬스터 공격 시 데미지 +1%"}],
                }],
                "champion_badge_total_info": [{"stat": "보스 몬스터 공격 시 데미지 +1%"}],
            }),
        }

        def fake_request(endpoint, params):
            self.assertEqual(params.get("ocid"), "sample-union-ocid")
            return payloads[endpoint]

        with patch("tracker.services.character_detail_service.request_nexon_api", side_effect=fake_request), patch(
            "tracker.services.character_detail_service._fetch_champion_image",
            return_value=None,
        ):
            result = get_character_detail_section("sample-union-ocid", "union")

        self.assertEqual(result["status"], "available")
        sources = {source["id"]: source for source in result["sources"]}
        self.assertEqual(
            set(sources),
            {"union", "unionStateStat", "unionArtifact", "unionChampion"},
        )
        self.assertEqual(sources["unionStateStat"]["presets"][1]["number"], 2)
        self.assertEqual(
            sources["unionArtifact"]["currentData"]["union_artifact_crystal"][0]["name"],
            "주황버섯",
        )
        self.assertEqual(
            sources["unionChampion"]["currentData"]["union_champion"][0]["champion_grade"],
            "SSS",
        )

    def test_champion_image_enrichment_resolves_character_image(self):
        from tracker.services.character_detail_service import _enrich_champion_images

        source = {
            "currentData": {
                "union_champion": [{
                    "champion_name": "밍득",
                    "champion_grade": "SSS",
                    "champion_class": "아크메이지(썬,콜)",
                }]
            }
        }
        with patch(
            "tracker.services.character_detail_service._fetch_champion_image",
            return_value="https://example.com/character.png",
        ):
            result = _enrich_champion_images(source)
        self.assertEqual(
            result["currentData"]["union_champion"][0]["character_image"],
            "https://example.com/character.png",
        )

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError):
            get_character_detail_section("sample-ocid", "unknown")


if __name__ == "__main__":
    unittest.main()
