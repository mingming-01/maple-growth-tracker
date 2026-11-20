"""Regression tests for AI provider fallback orchestration."""
import logging
import requests
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tracker.integrations.ai_provider import ProviderError
from tracker.domain.ai_metrics import build_server_growth_metrics
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

    def test_success_log_records_provider_model_transport_and_validation_without_content(self):
        metadata = {
            "provider": "openrouter", "model_alias": "openrouter/free",
            "selected_model": "vendor/free-route", "http_status": 200,
            "elapsed_ms": 3400.0, "response_body_present": True,
            "content_present": True, "usage": {"completion_tokens": 120},
        }
        with self.assertLogs(service.__name__, level="INFO") as captured:
            returned = service._log_provider_success(
                "openrouter", metadata, validated=True, returned=True, cache_hit=False
            )

        self.assertIn('"provider": "openrouter"', captured.output[0])
        self.assertIn('"model_alias": "openrouter/free"', captured.output[0])
        self.assertIn('"selected_model": "vendor/free-route"', captured.output[0])
        self.assertIn('"http_status": 200', captured.output[0])
        self.assertIn('"backend_validated": true', captured.output[0])
        self.assertTrue(returned["report_returned"])

    def test_http_200_fact_failure_logs_precise_reason_and_response_metadata(self):
        error = ProviderError("invalid output", "provider_invalid_output")
        error.validation_reason = "unsupported_number"
        error.provider_metadata = {
            "provider": "openrouter", "model_alias": "openrouter/free",
            "selected_model": "vendor/free-route", "http_status": 200,
            "elapsed_ms": 3400, "response_body_present": True,
            "response_classification": "fact_validation_failed",
            "content_present": True, "finish_reason": "stop",
        }
        started = time.monotonic()
        with self.assertLogs(service.__name__, level="WARNING") as captured:
            service._log_provider_failure("openrouter", error, started, started + 50)
        self.assertIn('"http_status": 200', captured.output[0])
        self.assertIn('"validation_failure_reason": "unsupported_number"', captured.output[0])
        self.assertIn('"response_classification": "fact_validation_failed"', captured.output[0])

    def test_provider_failure_log_includes_status_and_error_code_without_upstream_message(self):
        response = type("Response", (), {
            "status_code": 400,
            "text": '{"error":{"code":"unsupported_parameter","message":"Bad request. Bearer secret-value"}}',
        })()
        error = requests.HTTPError("400 Bad Request", response=response)
        started_at = time.monotonic()

        with self.assertLogs(service.__name__, level="WARNING") as captured:
            service._log_provider_failure(
                "openrouter", error, started_at, started_at + 10
            )

        self.assertIn('"http_status": 400', captured.output[0])
        self.assertIn('"provider_error_code": "unsupported_parameter"', captured.output[0])
        self.assertNotIn("Bad request.", captured.output[0])
        self.assertNotIn("secret-value", captured.output[0])

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini", return_value=(
        "[성장 패턴] 잘못된 모델 수치 999조\\n"
        "[성장 변화] 모델이 임의로 만든 변화예요.\\n"
        "[레벨업 분석] 모델이 임의로 만든 레벨 변화예요.\\n"
        "[성장 전망] 모델이 임의로 만든 날짜예요.\\n"
        "[AI 코멘트] 최근 기록을 더 쌓아가며 변화가 이어지는지 살펴보면 좋아요."
    ))
    def test_server_composes_measured_facts_and_keeps_only_ai_comment(
        self, gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state
        self.state.openrouter_api_key = ""
        summary = {
            "startDate": "2026-11-18",
            "endDate": "2026-11-20",
            "observedExperienceSum": 1200000000000,
            "averageDailyExperience": 1200000000000,
            "validGrowthIntervals": 1,
            "levelUpIntervals": 1,
        }
        metrics = {
            "levelProgress": {"currentRate": 55.0, "remainingRate": 45.0},
            "levelUps": [{
                "date": "2026-11-18",
                "previousLevel": 279,
                "currentLevel": 280,
            }],
            "prediction": None,
        }
        insights = {
            "recentPeriod": {
                **summary,
                "validGrowthIntervals": 1,
            },
            "previousPeriod": {},
            "weekOverWeek": {"status": "insufficient_data"},
        }

        result = service.generate_ai_analysis(
            {**self.character, "level": 280},
            [],
            computed_metrics=metrics,
            growth_insights=insights,
            analysis_context={"periodDays": 7, "periodSummary": summary},
            force_refresh=True,
        )

        self.assertTrue(result["aiGenerated"])
        self.assertEqual(result["aiStatus"], "generated")
        self.assertIn("1.2조", result["analysis"])
        self.assertIn("11월 18일에 279레벨에서 280레벨", result["analysis"])
        self.assertIn("55.0%", result["analysis"])
        self.assertIn("최근 기록을 더 쌓아가며", result["analysis"])
        self.assertNotIn("999조", result["analysis"])
        gemini.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service.request_gemini", side_effect=ProviderError(
        "Gemini unavailable", "provider_unavailable"
    ))
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=(
        "[AI 코멘트] 이 캐릭터는 확인된 사실과 무관하게 999% 상승했어요."
    ))
    def test_invalid_ai_comment_returns_un_cached_server_report(
        self, openrouter, _gemini, set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state
        result = service.generate_ai_analysis(
            self.character,
            [],
            computed_metrics={},
            growth_insights={},
            analysis_context={"periodDays": 7, "periodSummary": {}},
            force_refresh=True,
        )

        self.assertIn("analysis", result)
        self.assertFalse(result["aiGenerated"])
        self.assertEqual(result["aiStatus"], "fallback")
        self.assertIn("AI 코멘트를 생성하지 못했어요", result["analysis"])
        self.assertNotIn("999%", result["analysis"])
        set_cache.assert_not_called()
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini", side_effect=ProviderError(
        "Gemini unavailable", "provider_unavailable"
    ))
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    def test_server_calculated_level_up_growth_reaches_openrouter_prompt_and_returns_report(
        self, openrouter, _gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state
        records = [
            {
                "date": "2026-11-17", "level": 298,
                "experience": 1129263590513928, "experienceRate": 99.226,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-18", "level": 298,
                "experience": 1156066685461973, "experienceRate": 0.355,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-19", "level": 299,
                "experience": 17096549681346, "experienceRate": 0.984,
                "recordStatus": "available",
            },
        ]
        today = __import__("datetime").date(2026, 11, 19)
        calculated = build_server_growth_metrics(
            {"level": 299, "experienceRate": 0.984},
            records,
            reference_date=today,
            period_days=7,
        )
        self.assertEqual(calculated["metrics"]["observedChangeDays"], 0)
        self.assertIsNone(calculated["history"][1]["experienceChange"])
        self.assertTrue(calculated["history"][1]["levelUp"])
        self.assertTrue(calculated["history"][2]["levelUpCatchUp"])
        self.assertIsNone(calculated["history"][2]["experienceChange"])

        result = service.generate_ai_analysis(
            {
                "characterName": "밍득", "worldName": "크로아", "job": "아델",
                "level": 299, "experienceRate": 0.984,
            },
            calculated["history"],
            computed_metrics=calculated["metrics"],
            growth_insights={},
            analysis_context={
                "periodDays": 7,
                "periodSummary": calculated["periodSummary"],
            },
            force_refresh=True,
        )

        self.assertIn("analysis", result)
        self.assertTrue(result["analysis"].startswith("[성장 패턴]"))
        self.assertIn("[AI 코멘트]", result["analysis"])
        self.assertIn("현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요.", result["analysis"])
        prompt = openrouter.call_args.args[0]
        self.assertIn("레벨업 전환이 확인됨", prompt)
        self.assertNotIn('"experienceChange"', prompt)
        self.assertNotIn('"date":', prompt)
        self.assertNotIn("1156066685461973", prompt)
        self.assertNotIn("17096549681346", prompt)

    @patch("tracker.services.ai_analysis_service._request_deadline", return_value=12345.0)
    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini", side_effect=ProviderError(
        "Gemini unavailable", "provider_unavailable"
    ))
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache", side_effect=RuntimeError(
        "cache backend unavailable"
    ))
    def test_cache_write_failure_does_not_turn_successful_openrouter_report_into_failure(
        self, _cache_write, openrouter, _gemini, _cooldown, get_state, _deadline
    ):
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertIn("analysis", result)
        self.assertFalse(result["cacheHit"])
        self.assertTrue(result["analysis"].startswith("[성장 패턴]"))
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", side_effect=RuntimeError(
        "cache read unavailable"
    ))
    def test_cache_read_failure_is_treated_as_a_cache_miss(self, _cache_read):
        self.assertIsNone(service._get_cached_ai_response("cache-key"))

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
    def test_http_429_then_openrouter_timeout_returns_deterministic_report(
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

        self.assertIn("analysis", result)
        self.assertFalse(result["aiGenerated"])
        self.assertEqual(result["aiStatus"], "fallback")
        self.assertEqual(result["aiFallbackReason"], "provider_timeout")
        self.assertIn("AI 코멘트를 생성하지 못했어요", result["analysis"])
        self.assertTrue(self.state.ai_provider_state_store.saved)
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service.request_gemini")
    @patch("tracker.services.ai_analysis_service.request_openrouter", side_effect=[
        ProviderError("OpenRouter output was truncated", "provider_output_truncated"),
        VALID_REPORT,
    ])
    def test_http_429_then_truncated_openrouter_returns_fallback_without_retry(
        self, openrouter, gemini, _cooldown, _set_cache, _get_cache, get_state
    ):
        response = type("Response", (), {"status_code": 429, "headers": {}, "text": ""})()
        gemini.side_effect = requests.HTTPError("429 Too Many Requests", response=response)
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertIn("analysis", result)
        self.assertFalse(result["aiGenerated"])
        openrouter.assert_called_once()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=VALID_REPORT)
    @patch("tracker.services.ai_analysis_service._growth_report_fact_error")
    @patch("tracker.services.ai_analysis_service.request_gemini")
    def test_cached_server_report_skips_legacy_number_unit_allowlist(
        self, gemini, fact_error, _cache, get_state
    ):
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character,
            [],
            computed_metrics={},
            growth_insights={},
            analysis_context={"periodDays": 7, "periodSummary": {}},
        )

        self.assertTrue(result["cacheHit"])
        self.assertTrue(result["aiGenerated"])
        fact_error.assert_not_called()
        gemini.assert_not_called()

    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    @patch("tracker.services.ai_analysis_service.get_ai_response_cache", return_value=None)
    @patch("tracker.services.ai_analysis_service.set_ai_response_cache")
    @patch("tracker.services.ai_analysis_service._gemini_cooldown_remaining", return_value=0)
    @patch("tracker.services.ai_analysis_service._growth_report_fact_error", side_effect=["unsupported_number", True])
    @patch("tracker.services.ai_analysis_service.request_gemini", side_effect=ProviderError(
        "Gemini unavailable", "provider_unavailable"
    ))
    @patch("tracker.services.ai_analysis_service.request_openrouter", return_value=VALID_REPORT)
    def test_openrouter_comment_does_not_use_legacy_numeric_allowlist(
        self, openrouter, _gemini, _facts, _cooldown, _set_cache, _get_cache, get_state
    ):
        get_state.return_value = self.state

        result = service.generate_ai_analysis(
            self.character, [], computed_metrics={}, force_refresh=True
        )

        self.assertIn("analysis", result)
        self.assertTrue(result["aiGenerated"])
        self.assertEqual(openrouter.call_count, 1)
        _facts.assert_not_called()

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
