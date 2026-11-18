"""OpenRouter fallback timeout and retry-budget tests."""
import unittest
from unittest.mock import Mock, patch

import requests
from flask import Flask

from tracker.integrations.ai_provider import request_openrouter


class OpenRouterTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update({
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "openrouter/free",
            "OPENROUTER_CONNECT_TIMEOUT": 2.5,
            "OPENROUTER_READ_TIMEOUT": 6.5,
        })

    @patch("tracker.integrations.ai_provider.request_with_retries")
    def test_uses_short_split_timeout_and_single_attempt(self, request):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "성장 분석 결과"}}]
        }
        request.return_value = response

        with self.app.app_context():
            result = request_openrouter("prompt")

        self.assertEqual(result, "성장 분석 결과")
        self.assertEqual(request.call_args.kwargs["timeout"], (2.5, 6.5))
        self.assertEqual(request.call_args.kwargs["max_attempts"], 1)
        self.assertEqual(request.call_args.kwargs["backoff_factor"], 0)
        self.assertEqual(request.call_args.kwargs["max_retry_after_wait"], 0)

    @patch("tracker.integrations.ai_provider.request_with_retries")
    def test_upstream_503_is_not_retried(self, request):
        response = Mock()
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError(
            "upstream unavailable", response=Mock(status_code=503)
        )
        request.return_value = response

        with self.app.app_context(), self.assertRaises(requests.HTTPError):
            request_openrouter("prompt")

        self.assertEqual(request.call_args.kwargs["max_attempts"], 1)
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
