"""Regression tests for AI provider fallback orchestration."""
import logging
import requests
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tracker.integrations.ai_provider import ProviderError
from tracker.services import ai_analysis_service as service


VALID_REPORT = """[성장 패턴]
최근 성장 흐름을 확인했어요.
[성장 변화]
확인된 경험치 변화가 있어요.
[레벨업 분석]
현재 레벨 진행 상황을 확인했어요.
[성장 전망]
서버 계산 결과를 참고해 주세요.
[AI 코멘트]
기록을 계속 확인해 주세요."""


class FakeProviderStateStore:
    def __init__(self):
        self.cooldown_until = 0
        self.saved = []

    def get_cooldown_until(self, provider):
        return self.cooldown_until

    def set_cooldown_until(self, provider, until):
        self.cooldown_until = until
        self.saved.append((provider, until))

    def clear_cooldown(self, provider):
        self.cooldown_until = 0


class AIAnalysisFallbackTests(unittest.TestCase):
    def setUp(self):
        self.state = SimpleNamespace(
            gemini_api_key="gemini-key",
            openrouter_api_key="openrouter-key",
            ai_provider_state_store=FakeProviderStateStore(),
        )
        self.character = {
            "characterName": "테스트",
            "worldName": "스카니아",
            "job": "전사",
            "level": 280,
            "experienceRate": 12.5,
        }

    def test_provider_failure_logging_works_without_flask_app_context(self):
        started_at = time.monotonic()
        deadline = started_at + 10
        error = ProviderError("temporary provider failure", "provider_timeout")

        with self.assertLogs(service.__name__, level="WARNING") as captured:
            service._log_provider_failure("gemini", error, started_at, deadline)

        self.assertIn('"provider": "gemini"', captured.output[0])
        self.assertIn('"error_type": "provider_timeout"', captured.output[0])
        self.assertNotIn("temporary provider failure", captured.output[0])

    @patch("tracker.services.ai_analysis_service._request_deadline", return_value=12345.0)
    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.validate_growth_report", return_value=True)
    @patch("tracker.services.ai_analysis_service.sanitize_ai_text", side_effect=lambda value, *_: value)
    @patch("tracker.services.ai_analysis_service.request_gemini")
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    def test_http_429_falls_back_successfully_with_same_prompt_and_deadline(
        self, openrouter, gemini, _sanitize, _validate, _cooldown,
        _set_cache, _get_cache, get_state, _deadline
    ):
        response = type("Response", (), {"status_code": 429, "headers": {}, "text": ""})()
        gemini.side_effect = requests.HTTPError("429 Too Many Requests", response=response)
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [{"date": "2026-11-18", "experienceChange": 123}],
            computed_metrics={"experienceGained": 123}, force_refresh=True,
        )

        self.assertTrue(result["analysis"].startswith("[성장 패턴]"))
        gemini.assert_called_once()
        openrouter.assert_called_once()
        self.assertEqual(gemini.call_args.args[0], openrouter.call_args.args[0])
        self.assertEqual(gemini.call_args.kwargs["deadline"], 12345.0)
        self.assertEqual(openrouter.call_args.kwargs["deadline"], 12345.0)

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini")
    @patch("tracker.services.ai_analysis_service.request_openrouter", side_effect=requests.Timeout("read timeout"))
    def test_http_429_then_openrouter_timeout_returns_structured_503(
        self, openrouter, gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        response = type("Response", (), {
            "status_code": 429,
            "headers": {"Retry-After": "600"},
            "text": "",
        })()
        gemini.side_effect = requests.HTTPError("429 Too Many Requests", response=response)
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertEqual(result["statusCode"], 503)
        self.assertEqual(result["errorType"], "provider_fallback_failed")
        self.assertEqual(result["primaryErrorType"], "provider_quota")
        self.assertEqual(result["fallbackErrorType"], "provider_timeout")
        self.assertTrue(self.state.ai_provider_state_store.saved)
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini")
    @patch("tracker.services.ai_analysis_service.request_openrouter", side_effect=ProviderError(
        "OpenRouter output was truncated", "provider_output_truncated"
    ))
    def test_http_429_then_truncated_openrouter_returns_error_without_retry(
        self, openrouter, gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        response = type("Response", (), {"status_code": 429, "headers": {}, "text": ""})()
        gemini.side_effect = requests.HTTPError("429 Too Many Requests", response=response)
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertEqual(result["statusCode"], 503)
        self.assertEqual(result["errorType"], "provider_fallback_failed")
        self.assertEqual(result["fallbackErrorType"], "provider_output_truncated")
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.validate_growth_report", return_value=True)
    @patch("tracker.services.ai_analysis_service.sanitize_ai_text", side_effect=lambda value, *_: value)
    @patch("tracker.services.ai_analysis_service.request_gemini", side_effect=ProviderError(
        "Gemini returned no text", "provider_empty_response"
    ))
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    def test_gemini_empty_response_falls_back_to_openrouter(
        self, openrouter, _gemini, _sanitize, _validate, _cooldown,
        _set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertIn("analysis", result)
        self.assertFalse(result["cacheHit"])
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini", return_value="[AI 코멘트]\n주말 사냥이 평일보다 5% 효율적이에요.")
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    def test_gemini_incomplete_five_section_report_falls_back(
        self, openrouter, _gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state
        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )
        self.assertTrue(result["analysis"].startswith("[성장 패턴]"))
        openrouter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
