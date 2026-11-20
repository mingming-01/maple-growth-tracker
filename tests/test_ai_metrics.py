"""서버 계산 성장 지표 검증."""
import unittest
from datetime import date, timedelta

from tracker.domain.ai_metrics import build_server_growth_metrics


class ServerAIMetricsTests(unittest.TestCase):

    def test_server_metrics_include_period_summary_and_timeline_for_all_clients(self):
        today = date(2026, 11, 16)
        records = [
            {"date": "2026-11-13", "level": 280, "experience": 1000, "experienceRate": 10.0, "ranking": 300, "rankingScope": "overall", "rankingSourceDate": "2026-11-13", "recordStatus": "available"},
            {"date": "2026-11-14", "level": 280, "experience": 1200, "experienceRate": 12.0, "ranking": 280, "rankingScope": "overall", "rankingSourceDate": "2026-11-14", "recordStatus": "available"},
            {"date": "2026-11-15", "level": 280, "experience": 1200, "experienceRate": 12.0, "ranking": None, "recordStatus": "not_ready"},
            {"date": "2026-11-16", "level": None, "experience": None, "experienceRate": None, "recordStatus": "not_collected"},
        ]
        result = build_server_growth_metrics({"experienceRate": 12.0}, records, reference_date=today, period_days=4)
        summary = result["periodSummary"]
        self.assertEqual(result["metrics"]["averageDailyGrowth"], 200)
        self.assertEqual(result["metrics"]["sevenDayGrowth"], 200)
        self.assertEqual(result["metrics"]["rankingChange"], 20)
        self.assertEqual(summary["growth"], 200)
        self.assertEqual(summary["averageGrowth"], 200)
        self.assertEqual(summary["confirmedChangeDays"], 1)
        self.assertEqual(summary["availableDays"], 2)
        self.assertEqual(summary["notReadyDays"], 1)
        self.assertEqual(summary["notCollectedDays"], 1)
        self.assertEqual(summary["coveragePercent"], 50.0)
        self.assertEqual(result["metrics"]["timeline"][0]["type"], "best-growth")
        self.assertEqual(result["metrics"]["timeline"][0]["date"], "2026-11-14")
        self.assertIn(
            {"type": "latest", "date": "2026-11-14", "title": "최근 정상 기록",
             "description": "Lv. 280 · 경험치 1,200", "priority": 3},
            result["metrics"]["timeline"],
        )
        self.assertIsNone(result["metrics"]["prediction"])

    def test_metrics_are_derived_from_contiguous_authoritative_records(self):
        today = date(2026, 11, 16)
        records = [
            {
                "date": (today - timedelta(days=offset)).isoformat(),
                "level": 280,
                "experience": 1000 + (6 - offset) * 100,
                "ranking": 100 - (6 - offset),
                "recordStatus": "available",
            }
            for offset in range(7)
        ]
        result = build_server_growth_metrics(
            {"experienceRate": 42.5}, records, reference_date=today, period_days=7
        )

        self.assertEqual(result["metrics"]["observedChangeDays"], 6)
        self.assertEqual(result["metrics"]["averageDailyGrowth"], 100)
        self.assertEqual(result["metrics"]["levelProgress"]["currentRate"], 42.5)
        self.assertEqual(result["metrics"]["levelProgress"]["remainingRate"], 57.5)
        self.assertIsNone(result["metrics"]["prediction"])
        self.assertEqual(len(result["history"]), 7)

    def test_unverified_legacy_rank_is_excluded_from_ai_inputs(self):
        today = date(2026, 11, 16)
        records = [
            {
                "date": "2026-11-15",
                "level": 280,
                "experience": 1000,
                "ranking": 77,
                "rankingScope": "overall",
                "rankingSourceDate": None,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-16",
                "level": 280,
                "experience": 1100,
                "ranking": 66,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-15",
                "recordStatus": "available",
            },
        ]

        result = build_server_growth_metrics(
            {"experienceRate": 42.5}, records, reference_date=today, period_days=7
        )

        self.assertEqual(
            [item["ranking"] for item in result["history"]],
            [None, None],
        )
        self.assertIsNone(result["metrics"]["rankingChange"])

    def test_ai_rank_change_requires_two_consecutive_verified_overall_ranks(self):
        today = date(2026, 11, 16)
        records = [
            {
                "date": "2026-11-13",
                "level": 280,
                "experience": 1000,
                "ranking": 300,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-13",
                "recordStatus": "available",
            },
            {
                "date": "2026-11-14",
                "level": 280,
                "experience": 1100,
                "ranking": 280,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-14",
                "recordStatus": "available",
            },
            {
                "date": "2026-11-16",
                "level": 280,
                "experience": 1200,
                "ranking": 250,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-16",
                "recordStatus": "available",
            },
        ]

        result = build_server_growth_metrics(
            {"experienceRate": 42.5}, records, reference_date=today, period_days=7
        )

        self.assertEqual(result["history"][1]["rankingChange"], 20)
        self.assertIsNone(result["history"][2]["rankingChange"])
        self.assertEqual(result["metrics"]["rankingChange"], None)

    def test_zero_and_fractional_rank_values_are_rejected(self):
        today = date(2026, 11, 16)
        records = [
            {
                "date": "2026-11-15",
                "level": 280,
                "experience": 1000,
                "ranking": 0,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-15",
                "recordStatus": "available",
            },
            {
                "date": "2026-11-16",
                "level": 280,
                "experience": 1100,
                "ranking": 12.5,
                "rankingScope": "overall",
                "rankingSourceDate": "2026-11-16",
                "recordStatus": "available",
            },
        ]

        result = build_server_growth_metrics(
            {"experienceRate": 42.5}, records, reference_date=today, period_days=7
        )

        self.assertEqual([item["ranking"] for item in result["history"]], [None, None])

    def test_experience_rate_reset_uses_level_up_date_before_ranking_metadata_catches_up(self):
        today = date(2026, 11, 19)
        records = [
            {
                "date": "2026-11-17", "level": 298,
                "experience": 1129263590513928, "experienceRate": 99.226,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-18", "level": 298,
                "experience": 1156066685461973, "experienceRate": 0.355,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-19", "level": 299,
                "experience": 17096549681346, "experienceRate": 0.984,
                "recordStatus": "available",
            },
        ]

        result = build_server_growth_metrics(
            {"level": 299, "experienceRate": 0.984},
            records, reference_date=today, period_days=7
        )

        self.assertEqual(
            result["metrics"]["levelUps"],
            [{"date": "2026-11-18", "previousLevel": 298, "currentLevel": 299}],
        )
        self.assertTrue(result["history"][1]["levelUp"])
        self.assertIn(
            "당일 경험치 증가량 미확인",
            next(event["description"] for event in result["metrics"]["timeline"] if event["type"] == "level-up"),
        )
        self.assertFalse(result["history"][2]["levelUp"])
        self.assertTrue(result["history"][2]["levelUpCatchUp"])
        self.assertIsNone(result["history"][1]["experienceChange"])
        self.assertIsNone(result["history"][2]["experienceChange"])
        self.assertEqual(result["periodSummary"]["levelUpIntervals"], 1)
        self.assertEqual(result["metrics"]["observedChangeDays"], 0)
        self.assertIsNone(result["metrics"]["averageDailyGrowth"])
        self.assertEqual(result["periodSummary"]["validGrowthIntervals"], 0)
        self.assertIsNone(result["periodSummary"]["observedExperienceSum"])

    def test_missing_dates_and_level_up_transitions_are_not_interpolated(self):
        today = date(2026, 11, 16)
        records = [
            {"date": "2026-11-12", "level": 280, "experience": 1000, "recordStatus": "available"},
            {"date": "2026-11-13", "level": 280, "experience": 1100, "recordStatus": "available"},
            {"date": "2026-11-15", "level": 281, "experience": 20, "recordStatus": "available"},
            {"date": "2026-11-16", "level": 281, "experience": 120, "recordStatus": "available"},
            {"date": "2026-11-17", "level": 281, "experience": 999, "recordStatus": "available"},
        ]
        result = build_server_growth_metrics(
            {"experienceRate": 101}, records, reference_date=today, period_days=7
        )

        self.assertEqual(result["metrics"]["observedChangeDays"], 2)
        self.assertEqual(result["metrics"]["levelUps"], [])
        self.assertIsNone(result["metrics"]["levelProgress"]["currentRate"])
        self.assertEqual(len(result["history"]), 4)


if __name__ == "__main__":
    unittest.main()
