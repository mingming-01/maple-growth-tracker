"""Tests for bounded Gemini retries and provider fallback decisions."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from tracker.services.ai_analysis_service import _generate_gemini_content


class GeminiRetryTests(unittest.TestCase):
    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    def test_retries_transient_connection_failure(self, get_state, sleep):
        get_state.return_value = SimpleNamespace(
            ai_api_retries=1,
            ai_api_retry_backoff=0,
        )
        client = Mock()
        expected = Mock(text="성장 흐름이 안정적입니다.")
        client.models.generate_content.side_effect = [
            requests.Timeout("temporary timeout"),
            expected,
        ]

        result = _generate_gemini_content(client, "prompt")

        self.assertIs(result, expected)
        self.assertEqual(client.models.generate_content.call_count, 2)
        sleep.assert_not_called()

    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service.get_runtime_state")
    def test_does_not_retry_permanent_error(self, get_state, sleep):
        get_state.return_value = SimpleNamespace(
            ai_api_retries=3,
            ai_api_retry_backoff=0,
        )
        client = Mock()
        client.models.generate_content.side_effect = ValueError("invalid prompt")

        with self.assertRaises(ValueError):
            _generate_gemini_content(client, "prompt")

        self.assertEqual(client.models.generate_content.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
