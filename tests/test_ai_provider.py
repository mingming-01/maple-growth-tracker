"""Tests for wall-clock bounded Gemini and OpenRouter calls."""
import unittest
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


class AIProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update({
            "GEMINI_API_KEY": "gemini-test-key",
            "GEMINI_MODEL": "gemini-3.6-flash",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "openrouter/free",
            "AI_PROVIDER_CONNECT_TIMEOUT": 1.5,
            "AI_GEMINI_READ_TIMEOUT": 5.0,
            "AI_OPENROUTER_READ_TIMEOUT": 16.5,
            "AI_GEMINI_TOTAL_TIMEOUT": 7.0,
            "AI_OPENROUTER_TOTAL_TIMEOUT": 18.0,
        })

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
        self.assertEqual(post_json.call_args.kwargs["json_body"]["generationConfig"]["maxOutputTokens"], 640)

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_fallback_uses_short_total_deadline_and_no_streaming(self, post_json):
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
        self.assertEqual(post_json.call_args.kwargs["total_timeout"], 18.0)
        self.assertEqual(post_json.call_args.kwargs["read_timeout"], 16.5)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["stream"], False)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["max_tokens"], 4096)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["reasoning"], {"effort": "low"})

    @patch("tracker.integrations.ai_provider._log_openrouter_empty_response")
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
        deadline = 12345.0
        with self.app.app_context():
            request_gemini("prompt", deadline=deadline)
        self.assertEqual(post_json.call_args.kwargs["deadline"], deadline)

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


if __name__ == "__main__":
    unittest.main()
