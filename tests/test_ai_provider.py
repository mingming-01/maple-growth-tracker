"""Tests for wall-clock bounded Gemini and OpenRouter calls."""
import unittest
from unittest.mock import patch

import requests
from flask import Flask

from tracker.integrations.ai_provider import (
    request_gemini,
    request_openrouter,
    should_use_openrouter,
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
            "AI_OPENROUTER_READ_TIMEOUT": 11.0,
            "AI_GEMINI_TOTAL_TIMEOUT": 7.0,
            "AI_OPENROUTER_TOTAL_TIMEOUT": 14.0,
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
        self.assertEqual(post_json.call_args.kwargs["total_timeout"], 14.0)
        self.assertEqual(post_json.call_args.kwargs["read_timeout"], 11.0)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["stream"], False)
        self.assertEqual(post_json.call_args.kwargs["json_body"]["max_tokens"], 1536)

    @patch("tracker.integrations.ai_provider._log_openrouter_empty_response")
    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_empty_content_reports_safe_provider_metadata(self, post_json, log_metadata):
        post_json.return_value = {
            "id": "response-id",
            "choices": [{
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": None},
            }],
        }
        with self.app.app_context():
            with self.assertRaises(requests.RequestException):
                request_openrouter("private prompt text")

        details = log_metadata.call_args.kwargs
        self.assertEqual(details["finish_reason"], "stop")
        self.assertEqual(details["message_keys"], ["content", "role"])
        self.assertNotIn("private prompt text", repr(log_metadata.call_args))

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
