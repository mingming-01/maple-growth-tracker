"""서버 계산 성장 지표 검증."""
import unittest
from datetime import date, timedelta

from tracker.domain.ai_metrics import build_server_growth_metrics


class ServerAIMetricsTests(unittest.TestCase):
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
        self.assertEqual(result["metrics"]["levelUps"][0]["date"], "2026-11-15")
        self.assertIsNone(result["metrics"]["levelProgress"]["currentRate"])
        self.assertEqual(len(result["history"]), 4)


if __name__ == "__main__":
    unittest.main()
