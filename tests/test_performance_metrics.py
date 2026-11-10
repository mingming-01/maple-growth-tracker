import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from tracker.integrations import nexon_api
from tracker.services.performance_metrics import (
    PerformanceMetrics,
    get_performance_metrics,
)
from tracker import create_app, runtime


class PerformanceMetricsTests(unittest.TestCase):
    def test_counters_and_timing_percentiles_are_reported(self):
        metrics = PerformanceMetrics(sample_capacity=100)
        metrics.increment("nexon.attempts", endpoint="character/basic")
        metrics.increment("nexon.attempts", endpoint="character/basic")
        for value in (10, 20, 30, 40, 50):
            metrics.observe("http.request_ms", value, route="character.get_character")

        snapshot = metrics.snapshot()
        self.assertEqual(
            snapshot["counters"]["nexon.attempts{endpoint=character/basic}"],
            2,
        )
        timing = snapshot["timings"]["http.request_ms{route=character.get_character}"]
        self.assertEqual(timing["count"], 5)
        self.assertEqual(timing["p50"], 30)
        self.assertEqual(timing["p95"], 50)
        self.assertEqual(snapshot["scope"], "process-local")

    def test_sample_storage_is_bounded(self):
        metrics = PerformanceMetrics(sample_capacity=100)
        for value in range(250):
            metrics.observe("db.connection_ms", value, backend="sqlite")

        timing = metrics.snapshot()["timings"]["db.connection_ms{backend=sqlite}"]
        self.assertEqual(timing["count"], 100)
        self.assertEqual(timing["min"], 150)
        self.assertEqual(timing["max"], 249)

    def test_reset_clears_counters_and_samples(self):
        metrics = PerformanceMetrics()
        metrics.increment("cache.lookups", cache="character", result="hit")
        metrics.observe("http.request_ms", 12, route="character.get_character")
        metrics.reset()

        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["counters"], {})
        self.assertEqual(snapshot["timings"], {})

    def test_nexon_request_records_attempt_and_response(self):
        metrics = get_performance_metrics()
        metrics.reset()
        response = Mock(status_code=200)

        def request_with_metrics(*args, **kwargs):
            kwargs["on_attempt"](1)
            kwargs["on_response"](1, response, 2.5)
            return response

        with patch.object(
            nexon_api, "request_with_retries", side_effect=request_with_metrics
        ):
            result = nexon_api.request_nexon_api(
                "character/basic", {"ocid": "test-ocid"}
            )

        self.assertIs(result, response)
        counters = metrics.snapshot()["counters"]
        self.assertEqual(
            counters["nexon.logical_requests{endpoint=character/basic}"], 1
        )
        self.assertEqual(counters["nexon.attempts{endpoint=character/basic}"], 1)
        self.assertEqual(
            counters["nexon.responses{endpoint=character/basic,status=200}"], 1
        )


class AdminLogQueryMetricsTests(unittest.TestCase):
    def test_html_and_json_routes_record_each_query_separately(self):
        metrics = get_performance_metrics()
        metrics.reset()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                app = create_app({
                    "TESTING": True,
                    "GROWTH_DATABASE_URL": "",
                    "NEXON_API_KEY": "",
                })
                with app.app_context():
                    state = runtime.get_runtime_state()
                    state.log_db_backend = "sqlite"
                    state.log_db_path = os.path.join(temp_dir, "admin_logs.sqlite3")
                    runtime.initialize_log_db()

                client = app.test_client()
                with client.session_transaction() as session:
                    session["admin_authenticated"] = True

                self.assertEqual(client.get("/admin/api/logs").status_code, 200)
                self.assertEqual(client.get("/admin/logs").status_code, 200)

                snapshot = metrics.snapshot()
                for query_name in ("count", "page", "actions"):
                    labels = f"{{backend=sqlite,query={query_name},store=admin_logs}}"
                    self.assertEqual(
                        snapshot["counters"].get("db.query_executions" + labels),
                        2,
                    )
                    self.assertEqual(
                        snapshot["timings"]["db.query_ms" + labels]["count"],
                        2,
                    )
        finally:
            metrics.reset()


class PerformanceMetricsEndpointTests(unittest.TestCase):
    def test_performance_endpoint_requires_admin_session(self):
        app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
        })
        client = app.test_client()

        self.assertEqual(client.get("/admin/api/performance").status_code, 302)

        with client.session_transaction() as session:
            session["admin_authenticated"] = True

        response = client.get("/admin/api/performance")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["scope"], "process-local")


if __name__ == "__main__":
    unittest.main()
