import unittest
from datetime import date, timedelta

from tracker.domain.ai_growth_insights import build_growth_insights


class AIGrowthInsightsTests(unittest.TestCase):
    def make_records(self, start=date(2026, 10, 23), days=15):
        records = []
        experience = 1000
        for offset in range(days):
            current_date = start + timedelta(days=offset)
            if offset:
                experience += 112 if current_date >= date(2026, 10, 31) else 100
            records.append({
                "date": current_date.isoformat(),
                "level": 280,
                "experience": experience,
                "recordStatus": "available",
            })
        return records

    def test_compares_recent_seven_days_with_previous_seven_days(self):
        result = build_growth_insights(
            self.make_records(), reference_date="2026-11-06"
        )

        self.assertEqual(result["basis"]["referenceDate"], "2026-11-06")
        self.assertEqual(result["basis"]["expectedSnapshots"], 15)
        self.assertEqual(result["basis"]["availableSnapshots"], 15)
        self.assertEqual(result["basis"]["dataQuality"], "high")
        self.assertEqual(result["recentPeriod"]["validGrowthIntervals"], 7)
        self.assertEqual(result["previousPeriod"]["validGrowthIntervals"], 7)
        self.assertEqual(
            result["weekOverWeek"]["averageDailyGrowthChangePercent"], 12.0
        )
        self.assertEqual(result["weekOverWeek"]["direction"], "increase")

    def test_missing_calendar_day_is_not_interpolated(self):
        records = self.make_records()
        records = [item for item in records if item["date"] != "2026-10-27"]

        result = build_growth_insights(
            records, reference_date="2026-11-06"
        )

        self.assertEqual(result["basis"]["missingSnapshots"], 1)
        self.assertEqual(result["previousPeriod"]["validGrowthIntervals"], 5)
        # The missing date prevents a delta across the gap from being counted.
        self.assertEqual(
            result["weekOverWeek"]["status"], "available"
        )

    def test_level_up_transition_is_not_counted_as_experience_gain(self):
        records = self.make_records()
        level_up_record = next(item for item in records if item["date"] == "2026-10-30")
        level_up_record["level"] = 281
        level_up_record["experience"] = 25

        result = build_growth_insights(
            records, reference_date="2026-11-06"
        )

        self.assertEqual(result["previousPeriod"]["levelUpIntervals"], 1)
        self.assertEqual(result["previousPeriod"]["validGrowthIntervals"], 6)

    def test_experience_rate_reset_counts_on_reset_date_not_delayed_level_date(self):
        records = [
            {
                "date": "2026-11-12", "level": 298,
                "experience": 1034369058697585, "experienceRate": 91.228,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-13", "level": 298,
                "experience": 1056883268251231, "experienceRate": 93.284,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-14", "level": 298,
                "experience": 1094349410488372, "experienceRate": 94.825,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-15", "level": 298,
                "experience": 1103053861914765, "experienceRate": 96.177,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-16", "level": 298,
                "experience": 1118748264632899, "experienceRate": 97.143,
                "recordStatus": "available",
            },
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

        result = build_growth_insights(records, reference_date="2026-11-19")

        self.assertEqual(result["recentPeriod"]["levelUpIntervals"], 1)
        # The reset-day snapshot retains the exact same-level raw EXP delta.
        # Only the following date, where the recorded level changes, is excluded.
        self.assertEqual(result["recentPeriod"]["validGrowthIntervals"], 6)
        self.assertEqual(
            result["recentPeriod"]["observedExperienceSum"],
            121697626764388,
        )

    def test_already_calculated_history_is_aggregated_without_recomputing(self):
        records = self.make_records()
        for record in records:
            record["experienceChange"] = None
            record["levelUp"] = False
            record["levelUpCatchUp"] = False

        result = build_growth_insights(
            records,
            reference_date="2026-11-06",
            already_calculated=True,
        )

        # Raw EXP values could produce changes, but an already-normalized
        # backend result with None must remain unknown in AI aggregation.
        self.assertEqual(result["recentPeriod"]["validGrowthIntervals"], 0)
        self.assertIsNone(result["recentPeriod"]["observedExperienceSum"])
        self.assertEqual(result["previousPeriod"]["validGrowthIntervals"], 0)

    def test_insufficient_history_is_reported_without_a_percentage(self):
        records = self.make_records()[-7:]

        result = build_growth_insights(
            records, reference_date="2026-11-06"
        )

        self.assertEqual(result["basis"]["dataQuality"], "low")
        self.assertEqual(result["weekOverWeek"]["status"], "insufficient_data")
        self.assertIsNone(
            result["weekOverWeek"]["averageDailyGrowthChangePercent"]
        )
        self.assertEqual(result["weekdayWeekend"]["status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
