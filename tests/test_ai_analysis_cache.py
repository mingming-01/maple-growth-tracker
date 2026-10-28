import unittest
from unittest.mock import Mock, patch

import app as tracker
from tracker.services import ai_analysis_service


class AIResponseCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache_patch = patch.dict(tracker.AI_RESPONSE_CACHE, {}, clear=True)
        self.cache_patch.start()

    def tearDown(self):
        self.cache_patch.stop()

    def test_cache_reuses_only_the_same_prompt(self):
        tracker.set_ai_response_cache("prompt A", "저장된 분석")

        self.assertEqual(tracker.get_ai_response_cache("prompt A"), "저장된 분석")
        self.assertIsNone(tracker.get_ai_response_cache("prompt B"))

    def test_expired_cache_entry_is_removed(self):
        with patch.object(tracker.time, "time", return_value=1000):
            tracker.set_ai_response_cache("prompt", "오래된 분석")

        with patch.object(
            tracker.time,
            "time",
            return_value=1000 + tracker.AI_RESPONSE_CACHE_TTL + 1,
        ):
            self.assertIsNone(tracker.get_ai_response_cache("prompt"))

        self.assertEqual(tracker.AI_RESPONSE_CACHE, {})

    def test_growth_report_reuses_successful_model_response(self):
        client = Mock()
        client.models.generate_content.return_value = Mock(
            text=(
                "[성장 패턴] 꾸준한 흐름입니다.\n"
                "[성장 변화] 최근 기록에서 변화가 보입니다.\n"
                "[레벨업 분석] 확인된 레벨업은 없습니다.\n"
                "[성장 전망] 예측 자료를 참고하세요.\n"
                "[AI 코멘트] 기록을 이어가세요."
            )
        )
        character = {
            "characterName": "테스트캐릭터",
            "worldName": "크로아",
            "job": "히어로",
            "level": 280,
            "experienceRate": 42.5,
        }
        history = [{
            "date": "2026-10-26",
            "level": 280,
            "experienceChange": 12345,
            "ranking": 500,
            "rankingChange": 4,
            "levelUp": False,
        }]
        metrics = {
            "latestDailyGrowth": 12345,
            "averageDailyGrowth": 12345,
            "prediction": {"estimatedDate": "2026-11-01"},
        }

        with patch.object(ai_analysis_service, "gemini_client", client), patch.object(
            tracker, "OPENROUTER_API_KEY", ""
        ):
            first = tracker.generate_ai_analysis(character, history, metrics)
            second = tracker.generate_ai_analysis(character, history, metrics)

        self.assertEqual(first["analysis"], second["analysis"])
        self.assertFalse(first["cacheHit"])
        self.assertTrue(second["cacheHit"])
        client.models.generate_content.assert_called_once()

    def test_comparison_reuses_successful_model_response(self):
        client = Mock()
        client.models.generate_content.return_value = Mock(
            text="두 캐릭터의 성장 흐름은 기록된 범위에서 차이가 있습니다."
        )
        primary = {
            "character": {
                "characterName": "기준캐릭터",
                "worldName": "크로아",
                "job": "히어로",
                "level": 280,
                "experienceRate": 42.5,
                "ocid": "ignored-by-prompt",
            },
            "metrics": {"averageDailyGrowth": 1000, "rankingChange": 3},
            "history": [{
                "date": "2026-10-26",
                "level": 280,
                "experienceChange": 1000,
                "ranking": 500,
                "rankingChange": 3,
                "levelUp": False,
                "recordStatus": "available",
                "recordedAt": "volatile metadata",
            }],
        }
        comparison = {
            "character": {
                "characterName": "비교캐릭터",
                "worldName": "루나",
                "job": "팔라딘",
                "level": 279,
                "experienceRate": 65.0,
            },
            "metrics": {"averageDailyGrowth": 800, "rankingChange": -2},
            "history": [{
                "date": "2026-10-26",
                "level": 279,
                "experienceChange": 800,
                "ranking": 600,
                "rankingChange": -2,
                "levelUp": False,
                "recordStatus": "available",
            }],
        }

        with patch.object(ai_analysis_service, "gemini_client", client), patch.object(
            tracker, "OPENROUTER_API_KEY", ""
        ):
            first = tracker.generate_ai_comparison(primary, comparison)
            second = tracker.generate_ai_comparison(primary, comparison)

        self.assertEqual(first["analysis"], second["analysis"])
        self.assertFalse(first["cacheHit"])
        self.assertTrue(second["cacheHit"])
        client.models.generate_content.assert_called_once()

    def test_comparison_prompt_ignores_unrelated_character_metadata(self):
        client = Mock()
        client.models.generate_content.return_value = Mock(
            text="두 캐릭터를 기록된 범위에서 비교했습니다."
        )
        primary = {
            "character": {
                "characterName": "기준캐릭터",
                "worldName": "크로아",
                "job": "히어로",
                "level": 280,
                "experienceRate": 42.5,
                "dataAsOf": "2026-10-27T10:00:00+09:00",
            },
            "metrics": {"averageDailyGrowth": 1000},
            "history": [],
        }
        comparison = {
            "character": {
                "characterName": "비교캐릭터",
                "worldName": "루나",
                "job": "팔라딘",
                "level": 279,
                "experienceRate": 65.0,
            },
            "metrics": {"averageDailyGrowth": 800},
            "history": [],
        }

        with patch.object(ai_analysis_service, "gemini_client", client), patch.object(
            tracker, "OPENROUTER_API_KEY", ""
        ):
            first = tracker.generate_ai_comparison(primary, comparison)
            primary["character"]["dataAsOf"] = "2026-10-27T10:10:00+09:00"
            second = tracker.generate_ai_comparison(primary, comparison)

        self.assertEqual(first["analysis"], second["analysis"])
        self.assertTrue(second["cacheHit"])
        client.models.generate_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
