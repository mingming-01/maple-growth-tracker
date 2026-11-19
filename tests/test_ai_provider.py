"""Tests for wall-clock bounded Gemini and OpenRouter calls."""
import unittest
import time
from unittest.mock import patch

import requests
from flask import Flask

from tracker.integrations.ai_provider import (
    request_gemini,
    request_openrouter,
    should_use_openrouter,
    ProviderError,
    provider_retry_after_seconds,
)
from tracker.integrations.bounded_http import InvalidProviderResponse
from tracker.config import DEFAULT_OPENROUTER_MODEL, _resolve_openrouter_model


class AIProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update({
            "GEMINI_API_KEY": "gemini-test-key",
            "GEMINI_MODEL": "gemini-3.6-flash",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "google/gemini-3.6-flash",
            "AI_PROVIDER_CONNECT_TIMEOUT": 1.5,
            "AI_GEMINI_READ_TIMEOUT": 5.0,
            "AI_OPENROUTER_READ_TIMEOUT": 25.0,
            "AI_GEMINI_TOTAL_TIMEOUT": 7.0,
            "AI_OPENROUTER_TOTAL_TIMEOUT": 27.0,
            "AI_OPENROUTER_MIN_REMAINING_SECONDS": 20.0,
            "AI_OPENROUTER_MAX_OUTPUT_TOKENS": 8192,
        })

    def test_openrouter_free_is_default_and_explicit_model_is_preserved(self):
        self.assertEqual(DEFAULT_OPENROUTER_MODEL, "openrouter/free")
        self.assertEqual(_resolve_openrouter_model(None), "openrouter/free")
        self.assertEqual(_resolve_openrouter_model("  "), "openrouter/free")
        self.assertEqual(_resolve_openrouter_model("vendor/paid-model"), "vendor/paid-model")

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_adapter_defaults_to_free_router(self, post_json):
        post_json.return_value = {"choices": [{"message": {"content": "응답"}}]}
        self.app.config.pop("OPENROUTER_MODEL")
        with self.app.app_context():
            request_openrouter("prompt")
        self.assertEqual(post_json.call_args.kwargs["json_body"]["model"], "openrouter/free")

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_gemini_rest_extracts_text_and_uses_total_deadline(self, post_json):
        post_json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "성장 패턴 분석"}, {"text": "입니다."}]}
            }]
        }
        with self.app.app_context():
            result = request_gemini("prompt")

        self.assertEqual(result, "성장 패턴 분석입니다.")
        self.assertEqual(post_json.call_args.args[0],
                         "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent")
        self.assertEqual(post_json.call_args.kwargs["headers"]["x-goog-api-key"], "gemini-test-key")
        self.assertEqual(post_json.call_args.kwargs["total_timeout"], 7.0)
        self.assertEqual(post_json.call_args.kwargs["read_timeout"], 5.0)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["generationConfig"]["maxOutputTokens"], 2048)

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_fallback_clamps_output_tokens_and_uses_extended_deadline(self, post_json):
        post_json.return_value = {
            "choices": [{"message": {"content": "대체 분석 결과"}}]
        }
        with self.app.app_context():
            result = request_openrouter("prompt")

        self.assertEqual(result, "대체 분석 결과")
        self.assertEqual(post_json.call_args.args[0],
                         "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(post_json.call_args.kwargs["headers"]["Authorization"],
                         "Bearer openrouter-test-key")
        self.assertEqual(post_json.call_args.kwargs["total_timeout"], 27.0)
        self.assertEqual(post_json.call_args.kwargs["read_timeout"], 25.0)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["stream"], False)
        # Even when configured above the supported cap, the adapter must send at most 8192 tokens.
        self.assertEqual(post_json.call_args.kwargs["json_body"]["max_tokens"], 8192)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["reasoning"], {"effort": "low"})
        self.assertEqual(post_json.call_args.kwargs["json_body"]["model"], "google/gemini-3.6-flash")

    @patch("tracker.integrations.ai_provider._log_openrouter_empty_response")
    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_adapter_accepts_minimal_reasoning_retry(self, post_json):
        post_json.return_value = {"choices": [{"message": {"content": "재시도 응답"}}]}
        with self.app.app_context():
            result = request_openrouter("prompt", reasoning_effort="minimal")

        self.assertEqual(result, "재시도 응답")
        self.assertEqual(post_json.call_args.kwargs["json_body"]["reasoning"], {"effort": "minimal"})
        self.assertEqual(post_json.call_args.kwargs["json_body"]["model"], "google/gemini-3.6-flash")

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_empty_content_reports_safe_provider_metadata(self, post_json, log_metadata):
        post_json.return_value = {
            "id": "response-id",
            "model": "sample/free-model",
            "provider": "sample-provider",
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 1536,
                "total_tokens": 2736,
                "reasoning_tokens": 1500,
            },
            "choices": [{
                "finish_reason": "length",
                "native_finish_reason": "max_tokens",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning": "private reasoning must not be logged",
                },
            }],
        }
        with self.app.app_context():
            with self.assertRaises(requests.RequestException):
                request_openrouter("private prompt text")

        details = log_metadata.call_args.kwargs
        self.assertEqual(details["finish_reason"], "length")
        self.assertEqual(details["selected_model"], "sample/free-model")
        self.assertEqual(details["provider"], "sample-provider")
        self.assertEqual(details["usage"]["reasoning_tokens"], 1500)
        self.assertEqual(details["reasoning_length"], len("private reasoning must not be logged"))
        self.assertNotIn("private prompt text", repr(log_metadata.call_args))
        self.assertNotIn("private reasoning must not be logged", repr(log_metadata.call_args))

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_extracts_text_from_multimodal_content_parts(self, post_json):
        post_json.return_value = {
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": "대체 분석 "},
                        {"type": "text", "text": "완료"},
                    ]
                }
            }]
        }
        with self.app.app_context():
            result = request_openrouter("prompt")

        self.assertEqual(result, "대체 분석 완료")


    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_gemini_empty_http_200_is_fallback_eligible(self, post_json):
        post_json.return_value = {"candidates": [{"content": {"parts": []}}]}
        with self.app.app_context():
            with self.assertRaises(ProviderError) as caught:
                request_gemini("prompt")
        self.assertEqual(caught.exception.error_type, "provider_empty_response")
        self.assertTrue(should_use_openrouter(caught.exception))

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_length_finish_reason_is_truncated_even_with_partial_text(self, post_json):
        post_json.return_value = {
            "model": "sample/model",
            "choices": [{"finish_reason": "length", "message": {"content": "부분 응답"}}],
        }
        with self.app.app_context():
            with self.assertRaises(ProviderError) as caught:
                request_openrouter("prompt")
        self.assertEqual(caught.exception.error_type, "provider_output_truncated")
        post_json.assert_called_once()

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_empty_content_with_length_is_truncated(self, post_json):
        post_json.return_value = {
            "choices": [{"finish_reason": "length", "message": {"content": ""}}],
        }
        with self.app.app_context():
            with self.assertRaises(ProviderError) as caught:
                request_openrouter("prompt")
        self.assertEqual(caught.exception.error_type, "provider_output_truncated")
        post_json.assert_called_once()

    def test_actual_http_429_status_triggers_fallback(self):
        response = type("Response", (), {"status_code": 429, "headers": {}, "text": ""})()
        error = requests.HTTPError("429 Too Many Requests", response=response)
        self.assertTrue(should_use_openrouter(error))

    def test_retry_delay_from_gemini_error_body_is_used(self):
        response = type("Response", (), {
            "status_code": 429, "headers": {}, "text": '{"retryDelay":"61667s"}'
        })()
        error = requests.HTTPError("429", response=response)
        self.assertEqual(provider_retry_after_seconds(error, 300), 61667)

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_provider_deadline_is_forwarded_to_http_adapter(self, post_json):
        post_json.return_value = {"candidates": [{"content": {"parts": [{"text": "분석"}]}}]}
        deadline = time.monotonic() + 30.0
        with self.app.app_context():
            request_gemini("prompt", deadline=deadline)
        self.assertEqual(post_json.call_args.kwargs["deadline"], deadline)

    @patch("tracker.integrations.ai_provider.time.monotonic", return_value=100.0)
    def test_gemini_timeout_preserves_openrouter_budget(self, _clock):
        from tracker.integrations.ai_provider import _provider_timeouts
        with self.app.app_context():
            connect, read, total = _provider_timeouts("gemini", deadline=132.0)
        self.assertEqual(total, 7.0)
        self.assertLessEqual(connect + read, total)

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    @patch("tracker.integrations.ai_provider.time.monotonic", return_value=120.0)
    def test_gemini_is_skipped_when_only_fallback_budget_remains(self, _clock, post_json):
        with self.app.app_context():
            with self.assertRaises(requests.Timeout):
                request_gemini("prompt", deadline=139.0)
        post_json.assert_not_called()

    def test_gemini_deadline_and_http_504_trigger_fallback(self):
        self.assertTrue(should_use_openrouter(requests.Timeout("deadline exceeded")))
        error = requests.HTTPError("upstream timeout", response=type(
            "Response", (), {"status_code": 504}
        )())
        self.assertTrue(should_use_openrouter(error))

    def test_non_transient_authentication_error_does_not_trigger_fallback(self):
        error = requests.HTTPError("unauthorized", response=type(
            "Response", (), {"status_code": 401}
        )())
        self.assertFalse(should_use_openrouter(error))

    def test_success_status_with_invalid_provider_json_triggers_fallback(self):
        self.assertTrue(should_use_openrouter(InvalidProviderResponse("invalid JSON")))


if __name__ == "__main__":
    unittest.main()
