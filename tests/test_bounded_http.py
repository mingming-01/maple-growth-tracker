"""Regression tests for wall-clock bounded streamed JSON responses."""
import unittest
from unittest.mock import Mock, patch

import requests

from tracker.integrations.bounded_http import post_json_with_deadline


class BoundedJSONHTTPTests(unittest.TestCase):
    def make_response(self, chunks, status_code=200, reason="OK"):
        response = Mock()
        response.status_code = status_code
        response.reason = reason
        response.headers = {}
        response.iter_content.return_value = iter(chunks)
        response.close = Mock()
        return response

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.1, 10.2, 10.3, 10.4, 10.5])
    def test_reads_stream_and_parses_json(self, _clock, post):
        response = self.make_response([b'{"ok":true}'])
        post.return_value = response

        result = post_json_with_deadline(
            "https://provider.invalid", headers={}, json_body={"prompt": "x"}
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(post.call_args.kwargs["stream"], True)
        self.assertEqual(post.call_args.kwargs["timeout"], (1.5, 4.0))
        self.assertEqual(response.iter_content.call_args.kwargs["chunk_size"], 1)
        self.assertEqual(result.provider_metadata["http_status"], 200)
        self.assertEqual(result.provider_metadata["response_bytes"], len(b'{"ok":true}'))
        self.assertTrue(result.provider_metadata["response_body_present"])
        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.5, 11.1, 11.1])
    def test_stops_a_trickling_response_at_total_deadline(self, _clock, post):
        response = self.make_response([b"{", b'"', b"late"])
        response.headers = {"Content-Length": "10"}
        post.return_value = response

        with self.assertRaises(requests.Timeout) as caught:
            post_json_with_deadline(
                "https://provider.invalid",
                headers={},
                json_body={"prompt": "x"},
                total_timeout=1.0,
            )

        response.close.assert_called_once()
        self.assertEqual(caught.exception.provider_metadata["http_status"], 200)
        self.assertEqual(caught.exception.provider_metadata["response_classification"], "response_body_incomplete")
        self.assertFalse(caught.exception.provider_metadata["body_complete"])

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.1, 10.2, 10.3])
    def test_rejects_an_oversized_provider_response(self, _clock, post):
        response = self.make_response([b"x" * 1025])
        post.return_value = response

        with self.assertRaises(requests.RequestException):
            post_json_with_deadline(
                "https://provider.invalid",
                headers={},
                json_body={"prompt": "x"},
                max_response_bytes=1024,
            )

        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.1, 10.2, 10.3, 10.4, 10.5])
    def test_http_error_keeps_status_and_provider_error_body(self, _clock, post):
        response = self.make_response(
            [b'{"error":{"details":[{"retryDelay":"20s"}]}}'],
            status_code=429,
            reason="Too Many Requests",
        )
        post.return_value = response

        with self.assertRaises(requests.HTTPError) as caught:
            post_json_with_deadline(
                "https://provider.invalid", headers={}, json_body={"prompt": "x"}
            )

        self.assertEqual(caught.exception.response.status_code, 429)
        self.assertIn("retryDelay", str(caught.exception))
        self.assertEqual(caught.exception.provider_metadata["http_status"], 429)
        self.assertEqual(caught.exception.provider_metadata["provider_error_code"], None)
        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.1, 10.2, 10.3, 10.4, 10.5])
    def test_http_200_parse_failure_retains_status_and_safe_classification(self, _clock, post):
        response = self.make_response([b"not-json"])
        post.return_value = response

        with self.assertRaises(requests.RequestException) as caught:
            post_json_with_deadline(
                "https://provider.invalid", headers={}, json_body={"prompt": "private"}
            )

        self.assertEqual(caught.exception.provider_metadata["http_status"], 200)
        self.assertEqual(caught.exception.provider_metadata["response_classification"], "parse_error")
        self.assertNotIn("private", repr(caught.exception.provider_metadata))
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
