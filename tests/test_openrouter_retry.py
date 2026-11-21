"""Regression tests for bounded OpenRouter transport retries."""
import time
import unittest
from unittest.mock import patch

import requests

from tracker.integrations.ai_provider import ProviderError, ProviderText
from tracker.services.ai_analysis_service import _request_openrouter_with_retry


class OpenRouterRetryTests(unittest.TestCase):
    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service._log_provider_failure")
    @patch("tracker.services.ai_analysis_service.request_openrouter")
    def test_incomplete_response_body_retries_once_and_returns_second_attempt(
        self, request, log_failure, sleep
    ):
        first_error = requests.ConnectionError("response body interrupted")
        first_error.provider_metadata = {
            "http_status": 200,
            "response_bytes": 77,
            "body_complete": False,
            "response_classification": "response_body_incomplete",
        }
        request.side_effect = [
            first_error,
            ProviderText("정상 코멘트입니다.", {"response_mode": "sse", "stream_done": True}),
        ]

        result = _request_openrouter_with_retry(
            "prompt", api_key="test-key", deadline=time.monotonic() + 60,
            operation="openrouter_test",
        )

        self.assertEqual(result, "정상 코멘트입니다.")
        self.assertEqual(result.provider_metadata["attempt"], 2)
        self.assertEqual(result.provider_metadata["retry_count"], 1)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(0.25)
        log_failure.assert_called_once()
        self.assertEqual(log_failure.call_args.kwargs["attempt"], 1)

    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service._log_provider_failure")
    @patch("tracker.services.ai_analysis_service.request_openrouter")
    def test_authentication_failure_is_not_retried(self, request, log_failure, sleep):
        response = type("Response", (), {"status_code": 401, "headers": {}, "text": ""})()
        request.side_effect = requests.HTTPError("unauthorized", response=response)

        with self.assertRaises(requests.HTTPError):
            _request_openrouter_with_retry(
                "prompt", api_key="test-key", deadline=time.monotonic() + 60,
                operation="openrouter_test",
            )

        request.assert_called_once()
        sleep.assert_not_called()
        log_failure.assert_called_once()

    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service._log_provider_failure")
    @patch("tracker.services.ai_analysis_service.request_openrouter")
    def test_retry_is_skipped_when_remaining_deadline_is_too_small(
        self, request, log_failure, sleep
    ):
        error = requests.Timeout("response timed out")
        error.provider_metadata = {"response_classification": "response_body_incomplete"}
        request.side_effect = error

        with self.assertRaises(requests.Timeout):
            _request_openrouter_with_retry(
                "prompt", api_key="test-key", deadline=time.monotonic() + 4,
                operation="openrouter_test",
            )

        request.assert_called_once()
        sleep.assert_not_called()
        log_failure.assert_called_once()

    @patch("tracker.services.ai_analysis_service.time.sleep")
    @patch("tracker.services.ai_analysis_service._log_provider_failure")
    @patch("tracker.services.ai_analysis_service.request_openrouter")
    def test_empty_model_output_is_not_retried(self, request, log_failure, sleep):
        request.side_effect = ProviderError(
            "no report text", "provider_empty_response",
            provider_metadata={"response_classification": "reasoning_only"},
        )

        with self.assertRaises(ProviderError):
            _request_openrouter_with_retry(
                "prompt", api_key="test-key", deadline=time.monotonic() + 60,
                operation="openrouter_test",
            )

        request.assert_called_once()
        sleep.assert_not_called()
        log_failure.assert_called_once()


if __name__ == "__main__":
    unittest.main()
