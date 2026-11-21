"""Regression tests for wall-clock bounded JSON and SSE responses."""
import json
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
        self.assertEqual(response.iter_content.call_args.kwargs["chunk_size"], 4096)
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
        self.assertEqual(caught.exception.provider_metadata["timeout_cause"], "total_deadline")
        self.assertFalse(caught.exception.provider_metadata["body_complete"])

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", side_effect=[10.0, 10.5, 11.1, 11.1])
    def test_sse_deadline_failure_preserves_partial_stream_diagnostics(self, _clock, post):
        wire = (
            'data: {"choices":[{"delta":{"content":"partial text","reasoning":"internal trace"},"finish_reason":null}]}\\n\\n'
        ).encode("utf-8")
        response = self.make_response([wire])
        response.headers = {"Content-Type": "text/event-stream"}
        post.return_value = response

        with self.assertRaises(requests.Timeout) as caught:
            post_json_with_deadline(
                "https://provider.invalid",
                headers={"Accept": "text/event-stream"},
                json_body={"stream": True},
                total_timeout=1.0,
                response_format="sse",
            )

        metadata = caught.exception.provider_metadata
        self.assertEqual(metadata["response_mode"], "sse")
        self.assertEqual(metadata["stream_event_count"], 1)
        self.assertFalse(metadata["stream_done"])
        self.assertEqual(metadata["stream_content_bytes"], len("partial text"))
        self.assertEqual(metadata["stream_reasoning_bytes"], len("internal trace"))
        self.assertIsNone(metadata["stream_finish_reason"])
        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post", side_effect=requests.ReadTimeout("header wait timed out"))
    @patch("tracker.integrations.bounded_http.time.monotonic", return_value=10.0)
    def test_read_timeout_before_response_is_classified_as_response_headers(self, _clock, _post):
        with self.assertRaises(requests.ReadTimeout) as caught:
            post_json_with_deadline(
                "https://provider.invalid", headers={}, json_body={"prompt": "x"}
            )

        self.assertEqual(caught.exception.provider_metadata["timeout_phase"], "response_headers")
        self.assertEqual(caught.exception.provider_metadata["http_status"], None)
        self.assertEqual(caught.exception.provider_metadata["response_bytes"], 0)

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



    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", return_value=10.0)
    def test_sse_deltas_are_assembled_across_chunk_boundaries_and_done_is_required(self, _clock, post):
        wire = (
            'data: {"model":"vendor/free-route","provider":"route-a","choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}\r\n\r\n'
            'data: {"choices":[{"delta":{"content":"레벨업 "},"finish_reason":null}]}\r\n\r\n'
            'data: {"choices":[{"delta":{"content":"분석"},"finish_reason":"stop"}]}\r\n\r\n'
            'data: {"usage":{"prompt_tokens":12,"completion_tokens":8,"total_tokens":20}}\r\n\r\n'
            'data: [DONE]\r\n\r\n'
        ).encode("utf-8")
        chunks = [wire[index:index + 11] for index in range(0, len(wire), 11)]
        response = self.make_response(chunks)
        response.headers = {
            "Content-Type": "text/event-stream",
            "Transfer-Encoding": "chunked",
            "x-openrouter-request-id": "req-test-123",
        }
        post.return_value = response

        result = post_json_with_deadline(
            "https://provider.invalid",
            headers={"Accept": "text/event-stream"},
            json_body={"stream": True},
            response_format="sse",
        )

        self.assertEqual(result["choices"][0]["message"]["content"], "레벨업 분석")
        self.assertEqual(result["choices"][0]["finish_reason"], "stop")
        self.assertEqual(result["model"], "vendor/free-route")
        self.assertEqual(result["provider"], "route-a")
        self.assertEqual(result["usage"]["total_tokens"], 20)
        self.assertTrue(result.provider_metadata["stream_done"])
        self.assertEqual(result.provider_metadata["stream_event_count"], 4)
        self.assertEqual(result.provider_metadata["response_content_type"], "text/event-stream")
        self.assertEqual(result.provider_metadata["response_request_id"], "req-test-123")
        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", return_value=10.0)
    def test_auto_mode_detects_sse_even_when_request_requested_json(self, _clock, post):
        # The default JSON limit is 96 KiB. A route that responds with SSE must use
        # the larger bounded SSE allowance and stop at the explicit completion frame.
        generated_text = "x" * 100_000
        event = {
            "choices": [{
                "delta": {"content": generated_text},
                "finish_reason": "stop",
            }]
        }
        wire = (
            f"data: {json.dumps(event)}\n\n"
            "data: [DONE]\n\n"
        ).encode("utf-8")
        chunks = [wire[index:index + 4096] for index in range(0, len(wire), 4096)]
        response = self.make_response(chunks)
        response.headers = {"Content-Type": "text/event-stream"}
        post.return_value = response

        result = post_json_with_deadline(
            "https://provider.invalid",
            headers={},
            json_body={"stream": False},
            response_format="auto",
        )

        self.assertEqual(result["choices"][0]["message"]["content"], generated_text)
        self.assertEqual(result.provider_metadata["response_mode"], "sse")
        self.assertTrue(result.provider_metadata["stream_done"])
        response.close.assert_called_once()

    @patch("tracker.integrations.bounded_http.requests.post")
    @patch("tracker.integrations.bounded_http.time.monotonic", return_value=10.0)
    def test_sse_without_done_marker_is_rejected_as_incomplete(self, _clock, post):
        response = self.make_response([
            'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\n'.encode("utf-8")
        ])
        response.headers = {"Content-Type": "text/event-stream"}
        post.return_value = response

        with self.assertRaises(requests.RequestException) as caught:
            post_json_with_deadline(
                "https://provider.invalid",
                headers={},
                json_body={"stream": True},
                response_format="sse",
            )

        self.assertEqual(caught.exception.provider_metadata["response_classification"], "stream_incomplete")
        self.assertFalse(caught.exception.provider_metadata["stream_done"])
        self.assertTrue(caught.exception.provider_metadata["body_complete"])
        response.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
