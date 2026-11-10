import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app as tracker
from tracker import create_app
from tracker.controller import history_controller
from tracker.services import history_archive_service
from tracker.repositories.growth_history_store import GrowthHistoryStore
from tracker.runtime import get_runtime_state
from tracker.services.growth_history_service import GrowthHistoryService


class GrowthHistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = GrowthHistoryStore(
            sqlite_path=str(Path(self.temp_dir.name) / "growth_history.sqlite3")
        )
        self.today = date.today()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_only_valid_available_and_not_ready_records_are_saved(self):
        records = [
            {"date": self.today.isoformat(), "recordStatus": "available", "level": 280, "experience": 12345, "ranking": 100},
            {"date": (self.today - timedelta(days=1)).isoformat(), "recordStatus": "not_ready"},
            {"date": (self.today - timedelta(days=2)).isoformat(), "recordStatus": "unavailable"},
            {"date": "not-a-date", "recordStatus": "available", "level": 280, "experience": 12345},
        ]

        saved = self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", records)
        result = self.store.get_records(
            "test-ocid", self.today - timedelta(days=3), self.today
        )

        self.assertEqual(saved, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["recordStatus"], "not_ready")
        self.assertEqual(result[1]["recordStatus"], "available")
        self.assertEqual(result[1]["experience"], 12345)

    def test_experience_progress_rate_and_checked_flag_are_persisted(self):
        record_date = self.today.isoformat()
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드",
            [{
                "date": record_date,
                "recordStatus": "available",
                "level": 280,
                "experience": 12345,
                "ranking": 100,
                "experienceRate": "12.3456%",
                "experienceRateChecked": True,
            }],
        )

        result = self.store.get_records("test-ocid", self.today, self.today)

        self.assertEqual(result[0]["experienceRate"], 12.3456)
        self.assertTrue(result[0]["experienceRateChecked"])

    def test_same_character_and_date_is_upserted_instead_of_duplicated(self):
        record_date = self.today.isoformat()
        first = [{"date": record_date, "recordStatus": "available", "level": 280, "experience": 100, "ranking": 20}]
        updated = [{"date": record_date, "recordStatus": "available", "level": 281, "experience": 200, "ranking": 18}]

        self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", first)
        self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", updated)
        result = self.store.get_records("test-ocid", self.today, self.today)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["level"], 281)
        self.assertEqual(result[0]["experience"], 200)
        self.assertEqual(result[0]["ranking"], 18)

    def test_identical_growth_snapshot_is_not_updated(self):
        from tracker.services.performance_metrics import get_performance_metrics

        metrics = get_performance_metrics()
        metrics.reset()
        record = {
            "date": self.today.isoformat(),
            "recordStatus": "available",
            "level": 280,
            "experience": 12345,
            "ranking": 100,
            "experienceRate": 12.3456,
            "experienceRateChecked": True,
        }

        first_saved = self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드", [record]
        )
        self.assertEqual(first_saved, 1)

        connection = self.store._connect()
        try:
            with connection:
                connection.execute(
                    """
                    UPDATE growth_daily_snapshots
                    SET recorded_at = ?
                    WHERE ocid = ? AND snapshot_date = ?
                    """,
                    ("2000-01-01T00:00:00+00:00", "test-ocid", self.today.isoformat()),
                )
        finally:
            connection.close()

        before = self.store.get_records("test-ocid", self.today, self.today)[0]["recordedAt"]
        second_saved = self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드", [record]
        )
        after = self.store.get_records("test-ocid", self.today, self.today)[0]["recordedAt"]

        self.assertEqual(second_saved, 0)
        self.assertEqual(after, before)

        counters = metrics.snapshot()["counters"]
        self.assertEqual(
            counters["db.upsert_rows_attempted{backend=sqlite,store=growth_history}"],
            2,
        )
        self.assertEqual(
            counters["db.upsert_rows_affected{backend=sqlite,store=growth_history}"],
            1,
        )
        metrics.reset()

    def test_not_ready_does_not_overwrite_a_valid_record(self):
        record_date = self.today.isoformat()
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드",
            [{"date": record_date, "recordStatus": "available", "level": 280, "experience": 100, "ranking": 20}]
        )
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드",
            [{"date": record_date, "recordStatus": "not_ready"}]
        )
        result = self.store.get_records("test-ocid", self.today, self.today)

        self.assertEqual(result[0]["recordStatus"], "available")
        self.assertEqual(result[0]["experience"], 100)

    def test_date_range_is_inclusive_and_sorted(self):
        dates = [self.today - timedelta(days=2), self.today, self.today - timedelta(days=1)]
        records = [
            {"date": item.isoformat(), "recordStatus": "available", "level": 280, "experience": index + 1, "ranking": 50}
            for index, item in enumerate(dates)
        ]
        self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", records)

        result = self.store.get_records(
            "test-ocid", self.today - timedelta(days=1), self.today
        )

        self.assertEqual([item["date"] for item in result], [
            (self.today - timedelta(days=1)).isoformat(),
            self.today.isoformat()
        ])


    def test_api_rate_limit_is_shared_between_store_instances(self):
        store_path = str(Path(self.temp_dir.name) / "shared_limits.sqlite3")
        first_store = GrowthHistoryStore(sqlite_path=store_path)
        second_store = GrowthHistoryStore(sqlite_path=store_path)
        first = first_store.consume_api_rate_limit(
            client_key="same-client", now=1000.0, window_seconds=60,
            request_limit=1, refresh_limit=1,
        )
        second = second_store.consume_api_rate_limit(
            client_key="same-client", now=1001.0, window_seconds=60,
            request_limit=1, refresh_limit=1,
        )
        self.assertEqual(first, (True, 0, ""))
        self.assertEqual(second, (False, 59, "requests_per_minute"))

    def test_api_rate_limit_store_caps_client_entries(self):
        store_path = str(Path(self.temp_dir.name) / "cleanup_limits.sqlite3")
        store = GrowthHistoryStore(sqlite_path=store_path)
        for index in range(5):
            store.consume_api_rate_limit(
                client_key=f"client-{index}", now=1000.0 + index,
                window_seconds=60, request_limit=10, refresh_limit=10,
                max_clients=3,
            )
        store.consume_api_rate_limit(
            client_key="current-client", now=1005.0,
            window_seconds=60, request_limit=10, refresh_limit=10,
            max_clients=3, cleanup=True,
        )
        connection = store._connect()
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM api_request_limit_state"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertLessEqual(count, 3)

    def test_api_rate_limit_store_expires_inactive_clients(self):
        store_path = str(Path(self.temp_dir.name) / "expired_limits.sqlite3")
        store = GrowthHistoryStore(sqlite_path=store_path)
        store.consume_api_rate_limit(
            client_key="expired-client", now=1000.0,
            window_seconds=60, request_limit=10, refresh_limit=10,
        )
        store.consume_api_rate_limit(
            client_key="current-client", now=1300.0,
            window_seconds=60, request_limit=10, refresh_limit=10,
            cleanup=True,
        )
        connection = store._connect()
        try:
            keys = [
                row[0] for row in connection.execute(
                    "SELECT client_key FROM api_request_limit_state"
                ).fetchall()
            ]
        finally:
            connection.close()
        self.assertEqual(keys, ["current-client"])


    def test_concurrent_initialization_is_serialized_per_store(self):
        import threading

        errors = []

        def initialize():
            try:
                self.store.initialize()
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=initialize) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertTrue(self.store._initialized)


class GrowthHistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        })
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = GrowthHistoryStore(
            sqlite_path=str(Path(self.temp_dir.name) / "growth_history.sqlite3")
        )
        self.store.initialize()
        self.today = datetime.now(tracker.KOREA_TIMEZONE).date()
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드",
            [{
                "date": (self.today - timedelta(days=1)).isoformat(),
                "recordStatus": "available",
                "level": 280,
                "experience": 123456,
                "ranking": 321,
                "experienceRate": 12.345,
                "experienceRateChecked": True
            }]
        )
        with self.app.app_context():
            self.state = get_runtime_state()
            self.state.growth_history_repository = self.store
            self.state.growth_history_service = GrowthHistoryService(self.store)
            self.state.cache.clear()
            self.state.log_db_path = str(Path(self.temp_dir.name) / "admin_logs.sqlite3")
            self.state.log_db_backend = "sqlite"
            tracker.initialize_log_db()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            self.state.cache.clear()
        self.temp_dir.cleanup()

    def test_archive_returns_calendar_days_and_marks_missing_days(self):
        response = self.client.get("/api/history/archive?ocid=test-ocid&days=30")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body["history"]), 30)
        self.assertEqual(body["availableDays"], 1)
        self.assertEqual(body["notCollectedDays"], 29)
        saved_yesterday = body["history"][-2]
        self.assertEqual(saved_yesterday["recordStatus"], "available")
        self.assertEqual(saved_yesterday["experience"], 123456)
        self.assertEqual(body["history"][-1]["recordStatus"], "not_collected")

    def test_archive_keeps_each_characters_records_separate_for_comparison(self):
        target_date = (self.today - timedelta(days=1)).isoformat()
        self.store.save_records(
            "comparison-ocid", "비교캐릭터", "테스트월드",
            [{
                "date": target_date,
                "recordStatus": "available",
                "level": 279,
                "experience": 98765,
                "ranking": 654
            }]
        )

        primary_response = self.client.get("/api/history/archive?ocid=test-ocid&days=30")
        comparison_response = self.client.get("/api/history/archive?ocid=comparison-ocid&days=30")

        self.assertEqual(primary_response.status_code, 200)
        self.assertEqual(comparison_response.status_code, 200)
        primary_history = primary_response.get_json()["history"]
        comparison_history = comparison_response.get_json()["history"]
        self.assertEqual(primary_history[-2]["experience"], 123456)
        self.assertEqual(comparison_history[-2]["experience"], 98765)
        self.assertEqual(primary_history[-2]["ranking"], 321)
        self.assertEqual(comparison_history[-2]["ranking"], 654)

    def test_archive_does_not_fetch_past_data_without_collection_request(self):
        with patch.object(history_archive_service, "get_ranking_snapshot", side_effect=AssertionError("should not call Nexon")), patch.object(
            history_archive_service, "get_basic_character_snapshot", side_effect=AssertionError("should not call Nexon")
        ):
            response = self.client.get("/api/history/archive?ocid=test-ocid&days=30")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["collection"])

    def test_archive_collects_only_the_requested_missing_batch(self):
        ranking_response = Mock(status_code=200)
        basic_response = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 123456
        }
        with patch.object(
            history_controller, "get_basic_character_snapshot",
            return_value=(basic, basic_response)
        ) as verify_basic, patch.object(
            history_archive_service, "get_ranking_snapshot",
            side_effect=[(None, ranking_response), (None, ranking_response)]
        ) as get_ranking, patch.object(
            history_archive_service, "get_basic_character_snapshot",
            side_effect=[(basic, basic_response), (basic, basic_response)]
        ) as get_basic:
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                "&world_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%9B%94%EB%93%9C&offset=0&limit=2"
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(get_ranking.call_count, 2)
        self.assertEqual(verify_basic.call_count, 1)
        self.assertEqual(get_basic.call_count, 2)
        self.assertTrue(all(call.kwargs["historical"] for call in get_ranking.call_args_list))
        self.assertTrue(all(call.kwargs["historical"] for call in get_basic.call_args_list))
        self.assertEqual(body["collection"]["checkedDays"], 2)
        self.assertEqual(body["collection"]["savedRecords"], 2)
        self.assertEqual(body["collection"]["availableRecords"], 2)
        self.assertEqual(body["history"][0]["recordStatus"], "available")
        self.assertEqual(body["history"][1]["experience"], 123456)

        saved = self.store.get_records(
            "test-ocid", self.today - timedelta(days=29), self.today
        )
        self.assertEqual(len(saved), 3)

    def test_archive_collection_summary_only_omits_repeated_full_history_payload(self):
        ranking_response = Mock(status_code=200)
        basic_response = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 123456,
        }
        with patch.object(
            history_controller, "get_basic_character_snapshot",
            return_value=(basic, basic_response)
        ), patch.object(
            history_archive_service, "get_ranking_snapshot",
            return_value=(None, ranking_response),
        ), patch.object(
            history_archive_service, "get_basic_character_snapshot",
            return_value=(basic, basic_response),
        ):
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1&summary_only=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                "&world_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%9B%94%EB%93%9C&offset=0&limit=1"
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("collection", body)
        self.assertEqual(body["collection"]["checkedDays"], 1)
        self.assertNotIn("history", body)
        self.assertEqual(body["days"], 30)

    def test_archive_rechecks_not_ready_dates_when_user_requests_history(self):
        target_date = self.today - timedelta(days=2)
        self.store.save_records(
            "test-ocid", "테스트캐릭터", "테스트월드",
            [{"date": target_date.isoformat(), "recordStatus": "not_ready"}],
        )
        ranking_response = Mock(status_code=200)
        ranking = {"ranking": 123, "character_level": 280, "character_exp": 654321}

        current_basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 123456
        }
        with patch.object(
            history_controller, "get_basic_character_snapshot",
            return_value=(current_basic, Mock(status_code=200))
        ) as verify_basic, patch.object(
            history_archive_service, "get_ranking_snapshot", return_value=(ranking, ranking_response)
        ) as get_ranking, patch.object(
            history_archive_service, "get_basic_character_snapshot",
            return_value=(current_basic, Mock(status_code=200))
        ) as get_basic:
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                f"&offset={(target_date - (self.today - timedelta(days=29))).days}&limit=1"
            )

        self.assertEqual(response.status_code, 200)
        get_ranking.assert_called_once()
        self.assertTrue(get_ranking.call_args.kwargs["historical"])
        self.assertEqual(verify_basic.call_count, 1)
        self.assertEqual(get_basic.call_count, 1)
        self.assertTrue(all(call.kwargs["historical"] for call in get_basic.call_args_list))
        self.assertEqual(
            get_basic.call_args.kwargs["target_date"],
            target_date.isoformat(),
        )
        saved = self.store.get_records("test-ocid", target_date, target_date)
        self.assertEqual(saved[0]["recordStatus"], "available")
        self.assertEqual(saved[0]["experience"], 654321)
        self.assertEqual(saved[0]["ranking"], 123)

    def test_archive_does_not_save_api_parameter_errors_as_missing_data(self):
        invalid_response = Mock(status_code=400)
        current_basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 123456
        }
        with patch.object(
            history_controller, "get_basic_character_snapshot",
            return_value=(current_basic, Mock(status_code=200))
        ), patch.object(
            history_archive_service, "get_ranking_snapshot", return_value=(None, invalid_response)
        ), patch.object(
            history_archive_service, "get_basic_character_snapshot",
            return_value=(None, invalid_response)
        ):
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                "&offset=0&limit=1"
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["collection"]["savedRecords"], 0)
        self.assertEqual(body["collection"]["remainingDays"], 29)
        self.assertEqual(body["history"][0]["recordStatus"], "not_collected")
        saved_records = self.store.get_records(
            "test-ocid", self.today - timedelta(days=29), self.today
        )
        self.assertEqual(len(saved_records), 1)
        self.assertEqual(saved_records[0]["date"], (self.today - timedelta(days=1)).isoformat())
        self.assertEqual(saved_records[0]["recordStatus"], "available")

    def test_archive_rejects_collection_for_previous_period(self):
        previous_end = self.today - timedelta(days=30)
        response = self.client.get(
            f"/api/history/archive?ocid=test-ocid&days=30&collect=1"
            f"&character_name=test&end={previous_end.isoformat()}"
        )
        self.assertEqual(response.status_code, 400)

    def test_archive_accepts_custom_end_date_for_previous_period(self):
        end_date = self.today - timedelta(days=1)
        response = self.client.get(
            f"/api/history/archive?ocid=test-ocid&days=30&end={end_date.isoformat()}"
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["endDate"], end_date.isoformat())
        self.assertEqual(
            body["startDate"],
            (end_date - timedelta(days=29)).isoformat(),
        )
        self.assertEqual(body["history"][-1]["recordStatus"], "available")
        self.assertEqual(body["history"][-1]["experience"], 123456)

    def test_archive_rejects_unsupported_ranges_empty_ocid_and_bad_end_dates(self):
        today = datetime.now(tracker.KOREA_TIMEZONE).date()
        bad_range = self.client.get("/api/history/archive?ocid=test-ocid&days=365")
        missing_ocid = self.client.get("/api/history/archive?days=30")
        malformed_end = self.client.get(
            "/api/history/archive?ocid=test-ocid&days=30&end=tomorrow"
        )
        future_end = self.client.get(
            f"/api/history/archive?ocid=test-ocid&days=30&end={(today + timedelta(days=1)).isoformat()}"
        )
        too_old_end = self.client.get(
            f"/api/history/archive?ocid=test-ocid&days=30&end={(today - timedelta(days=61)).isoformat()}"
        )

        self.assertEqual(bad_range.status_code, 400)
        self.assertEqual(missing_ocid.status_code, 400)
        self.assertEqual(malformed_end.status_code, 400)
        self.assertEqual(future_end.status_code, 400)
        self.assertEqual(too_old_end.status_code, 400)

    def test_saved_recent_records_without_checked_rate_are_refreshed(self):
        today = datetime.now(tracker.KOREA_TIMEZONE).date()
        past_records = [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "recordStatus": "available",
                "level": 279,
                "experience": 10000 + offset,
                "ranking": 500 + offset,
                "experienceRate": None if offset in (1, 2) else 12.345,
                "experienceRateChecked": offset != 1,
            }
            for offset in range(1, 7)
        ]
        self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", past_records)
        response_stub = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 20000,
            "character_exp_rate": "23.4567",
        }
        ranking = {
            "ranking": 400,
            "character_level": 280,
            "character_exp": 20000,
            "character_exp_rate": "23.4567",
        }

        with patch.object(
            history_controller, "resolve_character",
            return_value=("test-ocid", basic, response_stub)
        ), patch.object(
            history_controller, "get_ranking_snapshot",
            return_value=(ranking, response_stub)
        ) as get_ranking:
            response = self.client.get(
                "/api/history?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0&refresh=1"
            )

        self.assertEqual(response.status_code, 200)
        requested_dates = {call.kwargs["target_date"] for call in get_ranking.call_args_list}
        self.assertEqual(
            requested_dates,
            {
                today.isoformat(),
                (today - timedelta(days=1)).isoformat(),
                (today - timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(get_ranking.call_count, 3)
        refreshed = self.store.get_records(
            "test-ocid", today - timedelta(days=1), today - timedelta(days=1)
        )
        self.assertEqual(refreshed[0]["experienceRate"], 23.4567)
        self.assertTrue(refreshed[0]["experienceRateChecked"])

    def test_saved_past_dates_are_reused_and_only_today_is_requested(self):
        today = datetime.now(tracker.KOREA_TIMEZONE).date()
        past_records = [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "recordStatus": "available",
                "level": 279,
                "experience": 10000 + offset,
                "ranking": 500 + offset,
                "experienceRate": 12.345,
                # This test covers reuse of fully checked historical records.
                "experienceRateChecked": True
            }
            for offset in range(1, 7)
        ]
        self.store.save_records("test-ocid", "테스트캐릭터", "테스트월드", past_records)
        response_stub = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 20000
        }
        today_ranking = {"ranking": 400, "character_level": 280, "character_exp": 20000}

        with patch.object(
            history_controller, "resolve_character",
            return_value=("test-ocid", basic, response_stub)
        ), patch.object(
            history_controller, "get_ranking_snapshot",
            return_value=(today_ranking, response_stub)
        ) as get_ranking:
            response = self.client.get("/api/history?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0&refresh=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_ranking.call_count, 1)
        history = response.get_json()["history"]
        self.assertEqual(history[-1]["experience"], 20000)
        self.assertEqual(history[0]["experience"], 10006)

    def test_history_request_saves_successful_recent_records(self):
        response_stub = Mock(status_code=200)
        basic = {
            "character_name": "테스트캐릭터",
            "world_name": "테스트월드",
            "character_level": 280,
            "character_exp": 100000
        }
        ranking = {
            "ranking": 100,
            "character_level": 280,
            "character_exp": 100000
        }

        with patch.object(
            history_controller, "resolve_character",
            return_value=("test-ocid", basic, response_stub)
        ), patch.object(
            history_controller, "get_ranking_snapshot",
            return_value=(ranking, response_stub)
        ):
            response = self.client.get("/api/history?name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0&refresh=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["historyStorage"]["status"], "saved")
        saved = self.store.get_records(
            "test-ocid", self.today - timedelta(days=6), self.today
        )
        self.assertEqual(len(saved), 7)
        self.assertTrue(all(row["recordStatus"] == "available" for row in saved))


if __name__ == "__main__":
    unittest.main()
