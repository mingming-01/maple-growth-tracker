"""Tests for bounded Gemini retries and provider fallback decisions."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from tracker.services.ai_analysis_service import _generate_gemini_content


class GeminiRetryTests(unittest.TestCase):
    def test_transient_failure_returns_immediately_for_provider_fallback(self):
        client = Mock()
        client.models.generate_content.side_effect = requests.Timeout("temporary timeout")

        with self.assertRaises(requests.Timeout):
            _generate_gemini_content(client, "prompt")

        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_permanent_error_is_not_retried(self):
        client = Mock()
        client.models.generate_content.side_effect = ValueError("invalid prompt")

        with self.assertRaises(ValueError):
            _generate_gemini_content(client, "prompt")

        self.assertEqual(client.models.generate_content.call_count, 1)


if __name__ == "__main__":
    unittest.main()
