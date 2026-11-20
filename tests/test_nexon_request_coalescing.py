"""Concurrent Nexon request coalescing regression tests."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import time
import unittest
from unittest.mock import Mock, patch

from tracker.integrations import nexon_api


class NexonRequestCoalescingTests(unittest.TestCase):
    def test_identical_concurrent_requests_share_one_upstream_call(self):
        response = Mock(status_code=200)
        release_upstream = Event()
        second_call_entered = Event()
        call_lock = Lock()
        upstream_calls = 0
        ready = [Event(), Event()]
        start = Event()

        def upstream_request(*_args, **_kwargs):
            nonlocal upstream_calls
            with call_lock:
                upstream_calls += 1
            release_upstream.wait(timeout=3)
            return response

        def invoke(index):
            ready[index].set()
            start.wait(timeout=2)
            if index == 1:
                second_call_entered.set()
            return nexon_api.request_nexon_api(
                "character/basic",
                {"ocid": "same-ocid"},
                timeout_override=(1, 1),
                max_attempts_override=1,
            )

        with (
            patch.object(nexon_api, "_throttle_nexon_request"),
            patch.object(
                nexon_api, "request_with_retries", side_effect=upstream_request
            ),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(invoke, 0)
                second = executor.submit(invoke, 1)
                self.assertTrue(ready[0].wait(timeout=1))
                self.assertTrue(ready[1].wait(timeout=1))
                start.set()
                self.assertTrue(second_call_entered.wait(timeout=1))
                time.sleep(0.1)
                calls_before_release = upstream_calls
                release_upstream.set()
                first_result = first.result(timeout=2)
                second_result = second.result(timeout=2)

        self.assertEqual(
            calls_before_release,
            1,
            "동일한 진행 중 Nexon 요청은 하나의 upstream 호출만 실행해야 합니다.",
        )
        self.assertEqual(upstream_calls, 1)
        self.assertIs(first_result, response)
        self.assertIs(second_result, response)


    def test_failed_request_is_removed_so_a_later_call_can_retry(self):
        response = Mock(status_code=200)
        with (
            patch.object(nexon_api, "_throttle_nexon_request"),
            patch.object(
                nexon_api,
                "request_with_retries",
                side_effect=[__import__("requests").Timeout("upstream timeout"), response],
            ) as upstream,
        ):
            with self.assertRaises(__import__("requests").Timeout):
                nexon_api.request_nexon_api(
                    "character/basic", {"ocid": "retry-ocid"},
                    timeout_override=(1, 1), max_attempts_override=1,
                )
            result = nexon_api.request_nexon_api(
                "character/basic", {"ocid": "retry-ocid"},
                timeout_override=(1, 1), max_attempts_override=1,
            )

        self.assertIs(result, response)
        self.assertEqual(upstream.call_count, 2)


if __name__ == "__main__":
    unittest.main()
