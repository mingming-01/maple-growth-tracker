"""Tests for bounded retries around external HTTP requests."""
import unittest
from unittest.mock import Mock, patch

import requests

from tracker.integrations.http_client import request_with_retries


class HttpClientRetryTests(unittest.TestCase):
    @staticmethod
    def response(status_code, headers=None):
        result = Mock()
        result.status_code = status_code
        result.headers = headers or {}
        return result

    @patch("tracker.integrations.http_client.time.sleep")
    @patch("tracker.integrations.http_client.requests.get")
    def test_returns_rate_limit_immediately_for_route_level_fallback(self, get, sleep):
        limited = self.response(429, {"Retry-After": "0"})
        get.return_value = limited

        result = request_with_retries(
            "get", "https://example.test/api",
            timeout=1, max_attempts=3, backoff_factor=0,
        )

        self.assertIs(result, limited)
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()
        limited.close.assert_not_called()

    @patch("tracker.integrations.http_client.time.sleep")
    @patch("tracker.integrations.http_client.requests.get")
    def test_preserves_retry_after_header_without_waiting_inside_request(self, get, sleep):
        limited = self.response(429, {"Retry-After": "12"})
        get.return_value = limited

        result = request_with_retries(
            "get", "https://example.test/api",
            timeout=1, max_attempts=2, backoff_factor=0.1, max_backoff=3,
        )

        self.assertIs(result, limited)
        self.assertEqual(result.headers["Retry-After"], "12")
        get.assert_called_once()
        sleep.assert_not_called()
        limited.close.assert_not_called()

    @patch("tracker.integrations.http_client.time.sleep")
    @patch("tracker.integrations.http_client.requests.get")
    def test_retries_connection_error_then_returns_success(self, get, sleep):
        success = self.response(200)
        get.side_effect = [requests.Timeout("temporary timeout"), success]

        result = request_with_retries(
            "get", "https://example.test/api",
            timeout=1, max_attempts=2, backoff_factor=0,
        )

        self.assertIs(result, success)
        self.assertEqual(get.call_count, 2)
        sleep.assert_not_called()

    @patch("tracker.integrations.http_client.requests.get")
    def test_does_not_retry_non_transient_client_error(self, get):
        bad_request = self.response(400)
        get.return_value = bad_request

        result = request_with_retries(
            "get", "https://example.test/api",
            timeout=1, max_attempts=3, backoff_factor=0,
        )

        self.assertIs(result, bad_request)
        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
