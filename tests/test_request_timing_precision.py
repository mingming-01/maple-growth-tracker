"""HTTP timing metrics retain sub-millisecond precision."""
from unittest import TestCase
from unittest.mock import patch

from flask import Flask

from tracker.runtime import record_user_action


class RequestTimingPrecisionTests(TestCase):
    def test_http_metric_keeps_fractional_milliseconds(self):
        app = Flask(__name__)
        with app.test_request_context("/metric-test"):
            from flask import request

            request.environ["maple_request_started_at"] = 10.0
            response = app.response_class("{}", status=200)

            with (
                patch("tracker.runtime.time.perf_counter", return_value=10.0004),
                patch("tracker.runtime.increment_metric") as increment,
                patch("tracker.runtime.observe_metric") as observe,
                patch("tracker.runtime.log_action"),
            ):
                result = record_user_action(response)

            self.assertIs(result, response)
            self.assertTrue(increment.called)
            http_timing = next(
                call for call in observe.call_args_list
                if call.args[0] == "http.request_ms"
            )
            self.assertAlmostEqual(http_timing.args[1], 0.4, places=6)
