"""구형 GET AI 분석 프롬프트와 응답 검증 규격의 일치 여부를 확인한다."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tracker.services.ai_analysis_service import generate_ai_analysis
from tracker.services.ai_text_service import REQUIRED_GROWTH_SECTIONS


VALID_LEGACY_REPORT = """[성장 패턴]
최근 기록은 비교할 자료가 많지 않아요.
[성장 변화]
확인된 날짜별 변화만 참고할 수 있어요.
[레벨업 분석]
기록에서 레벨 상승은 확인되지 않았어요.
[성장 전망]
예상 날짜를 판단할 정보가 충분하지 않아요.
[AI 코멘트]
새 기록이 쌓이면 흐름을 더 살펴볼 수 있어요."""


class LegacyAIPromptContractTests(unittest.TestCase):
    def test_legacy_prompt_requests_the_exact_sections_required_by_validator(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(
            text=VALID_LEGACY_REPORT
        )
        runtime_state = SimpleNamespace(
            openrouter_api_key=None,
            ai_api_retries=0,
            ai_api_retry_backoff=0,
        )

        with (
            patch(
                "tracker.services.ai_analysis_service.get_gemini_client",
                return_value=client,
            ),
            patch(
                "tracker.services.ai_analysis_service.get_runtime_state",
                return_value=runtime_state,
            ),
            patch(
                "tracker.services.ai_analysis_service.get_ai_response_cache",
                return_value=None,
            ),
            patch("tracker.services.ai_analysis_service.set_ai_response_cache") as save_cache,
        ):
            result = generate_ai_analysis(
                {
                    "characterName": "테스트캐릭터",
                    "worldName": "크로아",
                    "level": 280,
                },
                [],
                computed_metrics=None,
            )

        self.assertNotIn("error", result)
        self.assertEqual(result["analysis"], VALID_LEGACY_REPORT)
        prompt = client.models.generate_content.call_args.kwargs["contents"]
        positions = [prompt.index(section) for section in REQUIRED_GROWTH_SECTIONS]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), len(REQUIRED_GROWTH_SECTIONS))
        self.assertNotIn("[성장 분석]", prompt)
        self.assertNotIn("[레벨업]", prompt)
        self.assertNotIn("[AI 판단]", prompt)
        save_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
