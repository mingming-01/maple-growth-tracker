import unittest
from unittest.mock import patch

from tracker import create_app


class CharacterDetailControllerTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "FLASK_SECRET_KEY": "test-character-detail-secret-key-32-chars",
            "GROWTH_DATABASE_URL": "",
        })
        self.client = self.app.test_client()

    def test_requires_ocid_and_supported_section(self):
        missing_ocid = self.client.get("/api/character-details?section=stats")
        unknown_section = self.client.get(
            "/api/character-details?ocid=sample-ocid&section=unknown"
        )
        self.assertEqual(missing_ocid.status_code, 400)
        self.assertEqual(unknown_section.status_code, 400)

    def test_returns_partial_details_without_affecting_base_character_route(self):
        payload = {
            "section": "stats",
            "status": "partial",
            "sources": [
                {
                    "id": "stat",
                    "label": "주요 스탯",
                    "status": "available",
                    "activePresetNo": None,
                    "presets": [],
                    "data": {"final_stat": [{"stat_name": "전투력", "stat_value": "123"}]},
                    "combatPower": "123",
                },
                {
                    "id": "hyperStat",
                    "label": "하이퍼 스탯",
                    "status": "unavailable",
                    "message": "이 데이터는 현재 조회할 수 없습니다.",
                },
            ],
        }
        with patch(
            "tracker.controller.character_detail_controller.get_character_detail_section",
            return_value=payload,
        ), patch(
            "tracker.controller.character_detail_controller.record_best_combat_power",
            return_value={"value": 123, "observedAt": "2026-11-06T15:00:00+09:00", "presetNumbers": {"hyperStat": 1}},
        ):
            response = self.client.get(
                "/api/character-details?ocid=sample-ocid&section=stats"
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["sources"][0]["combatPower"], "123")
        self.assertEqual(body["sources"][1]["status"], "unavailable")
        self.assertEqual(body["bestCombatPower"], 123)
        self.assertEqual(body["bestPresetCombination"]["hyperStat"], 1)


if __name__ == "__main__":
    unittest.main()
