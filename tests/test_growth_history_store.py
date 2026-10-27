import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import app as tracker
from growth_history_store import GrowthHistoryStore


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


class GrowthHistoryApiTests(unittest.TestCase):
    def setUp(self):
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
                "ranking": 321
            }]
        )
        self.store_patch = patch.object(tracker, "growth_history_store", self.store)
        self.store_patch.start()
        tracker.CACHE.clear()
        self.client = tracker.app.test_client()

    def tearDown(self):
        tracker.CACHE.clear()
        self.store_patch.stop()
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
        with patch.object(tracker, "get_ranking", side_effect=AssertionError("should not call Nexon")), patch.object(
            tracker, "get_basic_character", side_effect=AssertionError("should not call Nexon")
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
            tracker, "get_ranking",
            side_effect=[(None, ranking_response), (None, ranking_response)]
        ) as get_ranking, patch.object(
            tracker, "get_basic_character",
            side_effect=[(basic, basic_response), (basic, basic_response), (basic, basic_response)]
        ) as get_basic:
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                "&world_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%9B%94%EB%93%9C&offset=0&limit=2"
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(get_ranking.call_count, 2)
        self.assertEqual(get_basic.call_count, 3)
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
            tracker, "get_ranking", return_value=(ranking, ranking_response)
        ) as get_ranking, patch.object(
            tracker, "get_basic_character", return_value=(current_basic, Mock(status_code=200))
        ) as get_basic:
            response = self.client.get(
                "/api/history/archive?ocid=test-ocid&days=30&collect=1"
                "&character_name=%ED%85%8C%EC%8A%A4%ED%8A%B8%EC%BA%90%EB%A6%AD%ED%84%B0"
                f"&offset={(target_date - (self.today - timedelta(days=29))).days}&limit=1"
            )

        self.assertEqual(response.status_code, 200)
        get_ranking.assert_called_once()
        self.assertTrue(get_ranking.call_args.kwargs["historical"])
        get_basic.assert_called_once()
        self.assertTrue(get_basic.call_args.kwargs["historical"])
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
            tracker, "get_ranking", return_value=(None, invalid_response)
        ), patch.object(
            tracker, "get_basic_character",
            side_effect=[(current_basic, Mock(status_code=200)), (None, invalid_response)]
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

    def test_saved_past_dates_are_reused_and_only_today_is_requested(self):
        today = datetime.now(tracker.KOREA_TIMEZONE).date()
        past_records = [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "recordStatus": "available",
                "level": 279,
                "experience": 10000 + offset,
                "ranking": 500 + offset
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

        with patch.object(tracker, "get_ocid", return_value=("test-ocid", response_stub)), patch.object(
            tracker, "get_basic_character", return_value=(basic, response_stub)
        ), patch.object(tracker, "get_ranking", return_value=(today_ranking, response_stub)) as get_ranking:
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

        with patch.object(tracker, "get_ocid", return_value=("test-ocid", response_stub)), patch.object(
            tracker, "get_basic_character", return_value=(basic, response_stub)
        ), patch.object(tracker, "get_ranking", return_value=(ranking, response_stub)):
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
