"""Regression tests for the expanded AI provider budgets."""
import unittest
from unittest.mock import patch

from tracker.integrations import ai_provider


class AIProviderLimitTests(unittest.TestCase):
    def test_non_request_context_deadline_defaults_to_ninety_seconds(self):
        from tracker.services import ai_analysis_service

        with patch.object(ai_analysis_service, "has_request_context", return_value=False), patch.object(ai_analysis_service.time, "monotonic", return_value=100.0):
            self.assertEqual(ai_analysis_service._request_deadline(), 190.0)

    def test_provider_timeouts_reserve_time_for_bounded_openrouter_retry(self):
        settings = {
            "AI_PROVIDER_CONNECT_TIMEOUT": 2.0,
            "AI_OPENROUTER_READ_TIMEOUT": 60.0,
            "AI_OPENROUTER_TOTAL_TIMEOUT": 65.0,
        }
        with patch.object(ai_provider, "_setting", side_effect=lambda name, default=None: settings.get(name, default)):
            self.assertEqual(ai_provider._provider_timeouts("openrouter"), (2.0, 43.0, 45.0))

    def test_gemini_timeout_reserves_time_for_openrouter_fallback(self):
        settings = {
            "AI_PROVIDER_CONNECT_TIMEOUT": 2.0,
            "AI_GEMINI_READ_TIMEOUT": 15.0,
            "AI_GEMINI_TOTAL_TIMEOUT": 18.0,
            "OPENROUTER_API_KEY": "fallback-key",
            "AI_OPENROUTER_MIN_REMAINING_SECONDS": 65.0,
        }
        with patch.object(ai_provider, "_setting", side_effect=lambda name, default=None: settings.get(name, default)), patch.object(ai_provider.time, "monotonic", return_value=100.0):
            self.assertEqual(
                ai_provider._provider_timeouts("gemini", deadline=190.0),
                (2.0, 15.0, 18.0),
            )

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_gemini_request_uses_expanded_output_limit(self, post_json):
        post_json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "report"}]}, "finishReason": "STOP"}]
        }

        self.assertEqual(ai_provider.request_gemini("prompt", api_key="test-key"), "report")
        payload = post_json.call_args.kwargs["json_body"]
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 2048)

    @patch("tracker.integrations.ai_provider.post_json_with_deadline")
    def test_openrouter_request_uses_expanded_default_output_limit(self, post_json):
        post_json.return_value = {
            "choices": [{"message": {"content": "report"}, "finish_reason": "stop"}]
        }

        self.assertEqual(ai_provider.request_openrouter("prompt", api_key="test-key"), "report")
        payload = post_json.call_args.kwargs["json_body"]
        self.assertEqual(payload["max_tokens"], 8192)
        self.assertEqual(payload["reasoning"], {"effort": "minimal", "max_tokens": 512})


if __name__ == "__main__":
    unittest.main()
