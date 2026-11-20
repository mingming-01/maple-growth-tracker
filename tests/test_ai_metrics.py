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
        self.assertEqual(result["metrics"]["prediction"]["progressSamples"], 1)
        self.assertEqual(result["metrics"]["prediction"]["averageDailyProgressRate"], 2.0)
        self.assertEqual(result["metrics"]["prediction"]["averageGrowth"], 200.0)
        self.assertEqual(result["metrics"]["prediction"]["requiredExp"], 8800)
        self.assertTrue(result["metrics"]["prediction"]["requiredExpEstimated"])
        self.assertEqual(result["metrics"]["prediction"]["days"], 44.0)
        self.assertEqual(result["metrics"]["prediction"]["date"], "2026-12-28")

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

    def test_thirty_day_trend_compares_calendar_halves_using_exact_observed_changes(self):
        today = date(2026, 11, 21)
        period_start = today - timedelta(days=29)
        records = []
        experience = 999900

        # 기간 시작일의 변화량도 구할 수 있도록 직전 날짜 스냅샷을 포함한다.
        for offset in range(-1, 30):
            current_date = period_start + timedelta(days=offset)
            if offset >= 0:
                experience += 100 if offset < 15 else 200
            records.append({
                "date": current_date.isoformat(),
                "level": 280,
                "experience": experience,
                "recordStatus": "available",
            })

        result = build_server_growth_metrics(
            {"level": 280}, records, reference_date=today, period_days=30
        )
        trend = result["metrics"]["periodTrend"]

        self.assertEqual(trend["status"], "available")
        self.assertEqual(trend["comparisonMethod"], "calendar_halves")
        self.assertEqual(trend["firstHalf"]["validGrowthIntervals"], 15)
        self.assertEqual(trend["firstHalf"]["observedExperienceSum"], 1500)
        self.assertEqual(trend["secondHalf"]["validGrowthIntervals"], 15)
        self.assertEqual(trend["secondHalf"]["observedExperienceSum"], 3000)
        self.assertEqual(trend["changePercent"], 100.0)
        self.assertEqual(trend["direction"], "increase")
        self.assertEqual(trend["strength"], "strong")

    def test_ninety_day_trend_compares_first_and_second_calendar_halves(self):
        today = date(2026, 11, 21)
        period_start = today - timedelta(days=89)
        records = []
        experience = 100000

        for offset in range(-1, 90):
            current_date = period_start + timedelta(days=offset)
            if offset >= 0:
                experience += 200 if offset < 45 else 100
            records.append({
                "date": current_date.isoformat(),
                "level": 280,
                "experience": experience,
                "recordStatus": "available",
            })

        result = build_server_growth_metrics(
            {"level": 280}, records, reference_date=today, period_days=90
        )
        trend = result["metrics"]["periodTrend"]

        self.assertEqual(trend["status"], "available")
        self.assertEqual(trend["firstHalf"]["validGrowthIntervals"], 45)
        self.assertEqual(trend["firstHalf"]["observedExperienceSum"], 9000)
        self.assertEqual(trend["secondHalf"]["validGrowthIntervals"], 45)
        self.assertEqual(trend["secondHalf"]["observedExperienceSum"], 4500)
        self.assertEqual(trend["changePercent"], -50.0)
        self.assertEqual(trend["direction"], "decrease")
        self.assertEqual(trend["strength"], "strong")

    def test_long_period_trend_keeps_missing_days_empty_and_includes_level_up_gain(self):
        today = date(2026, 11, 21)
        period_start = today - timedelta(days=29)
        records = []
        experience = 999900

        for offset in range(-1, 30):
            if offset == 5:
                # 빠진 날짜는 보간하지 않는다.
                continue
            current_date = period_start + timedelta(days=offset)
            if offset < 14:
                if offset >= 0:
                    experience += 100
                level = 280
                rate = 90.0 + offset * 0.7
            elif offset == 14:
                # 진행률 초기화가 확인된 레벨업 날짜의 EXP 차이는 미확정으로 유지한다.
                experience = 100
                level = 280
                rate = 0.5
            else:
                experience = 100 + (offset - 14) * 200
                level = 281
                rate = 0.5 + (offset - 14) * 0.2
            records.append({
                "date": current_date.isoformat(),
                "level": level,
                "experience": experience,
                "experienceRate": rate,
                "recordStatus": "available",
            })

        result = build_server_growth_metrics(
            {"level": 281}, records, reference_date=today, period_days=30
        )
        trend = result["metrics"]["periodTrend"]
        level_up_record = next(
            item for item in result["history"]
            if item["date"] == (period_start + timedelta(days=14)).isoformat()
        )

        self.assertTrue(level_up_record["levelUp"])
        self.assertIsNotNone(level_up_record["experienceChange"])
        self.assertEqual(level_up_record["experienceChangeKind"], "level_up_reconstructed")
        self.assertEqual(trend["firstHalf"]["validGrowthIntervals"], 13)
        self.assertEqual(trend["firstHalf"]["observedExperienceSum"], 1200)
        self.assertEqual(trend["firstHalf"]["experienceGainSum"], 10394)
        self.assertEqual(trend["firstHalf"]["reconstructedLevelUpIntervals"], 1)
        self.assertEqual(trend["secondHalf"]["validGrowthIntervals"], 15)
        self.assertEqual(trend["secondHalf"]["experienceGainSum"], 3000)
        self.assertEqual(trend["direction"], "decrease")

    def test_long_period_trend_requires_enough_observed_changes_in_both_halves(self):
        today = date(2026, 11, 21)
        period_start = today - timedelta(days=29)
        records = []
        experience = 1000
        offsets = [-1, 0, 1, 2, 3, 4, 14, 15, 16, 17, 18, 19]

        for offset in offsets:
            current_date = period_start + timedelta(days=offset)
            if offset >= 0:
                experience += 100 if offset < 15 else 200
            records.append({
                "date": current_date.isoformat(),
                "level": 280,
                "experience": experience,
                "recordStatus": "available",
            })

        result = build_server_growth_metrics(
            {"level": 280}, records, reference_date=today, period_days=30
        )
        trend = result["metrics"]["periodTrend"]

        self.assertEqual(trend["status"], "insufficient_data")
        self.assertEqual(trend["firstHalf"]["validGrowthIntervals"], 5)
        self.assertEqual(trend["secondHalf"]["validGrowthIntervals"], 5)
        self.assertEqual(trend["direction"], "insufficient_data")
        self.assertIsNone(trend["changePercent"])

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

    def test_level_up_boundary_gain_is_included_and_delayed_catch_up_drives_forecast(self):
        today = date(2026, 11, 20)
        records = [
            {"date": "2026-11-17", "level": 298, "experience": 1129263590513928, "experienceRate": 99.226, "recordStatus": "available"},
            {"date": "2026-11-18", "level": 298, "experience": 6175579914147, "experienceRate": 0.355, "recordStatus": "available"},
            {"date": "2026-11-19", "level": 299, "experience": 34219899249572, "experienceRate": 1.969, "recordStatus": "available"},
            {"date": "2026-11-20", "level": 299, "experience": 50805631039495, "experienceRate": 2.924, "recordStatus": "available"},
        ]

        result = build_server_growth_metrics(
            {"level": 299, "experienceRate": 2.924},
            records, reference_date=today, period_days=7
        )

        self.assertEqual(
            result["metrics"]["levelUps"],
            [{"date": "2026-11-18", "previousLevel": 298, "currentLevel": 299}],
        )
        self.assertTrue(result["history"][1]["levelUp"])
        self.assertEqual(result["history"][1]["experienceChange"], 14984259283040)
        self.assertEqual(result["history"][1]["experienceChangeKind"], "level_up_reconstructed")
        self.assertTrue(result["history"][2]["levelUpCatchUp"])
        self.assertEqual(result["history"][2]["experienceChange"], 28044319335425)
        self.assertEqual(result["history"][3]["experienceChange"], 16585731789923)
        self.assertEqual(result["metrics"]["observedChangeDays"], 2)
        self.assertEqual(result["metrics"]["calculatedChangeDays"], 3)
        expected_average = (14984259283040 + 28044319335425 + 16585731789923) / 3
        self.assertEqual(result["metrics"]["averageDailyGrowth"], expected_average)
        self.assertEqual(result["periodSummary"]["validGrowthIntervals"], 3)
        self.assertEqual(result["periodSummary"]["observedExperienceSum"], 44630051125348)
        self.assertEqual(result["periodSummary"]["experienceGainSum"], 59614310408388)
        self.assertEqual(result["periodSummary"]["reconstructedLevelUpExperienceSum"], 14984259283040)
        self.assertEqual(result["periodSummary"]["reconstructedLevelUpIntervals"], 1)

        prediction = result["metrics"]["prediction"]
        self.assertEqual(prediction["currentLevel"], 299)
        self.assertEqual(prediction["nextLevel"], 300)
        self.assertEqual(prediction["remainingRate"], 97.076)
        self.assertEqual(prediction["progressSamples"], 2)
        self.assertEqual(prediction["experienceSamples"], 2)
        self.assertEqual(prediction["averageGrowth"], 22315025562674.0)
        self.assertAlmostEqual(prediction["averageDailyProgressRate"], 1.2845)
        self.assertEqual(prediction["requiredExp"], 1686733050201784)
        self.assertTrue(prediction["requiredExpEstimated"])
        self.assertAlmostEqual(prediction["days"], 75.5873232349, places=8)
        self.assertEqual(prediction["date"], "2027-02-04")
        self.assertEqual(prediction["estimatedDate"], "2027-02-04")

    def test_period_totals_include_level_up_gain_without_mixing_it_into_exact_snapshot_sum(self):
        today = date(2026, 11, 18)
        records = [
            {
                "date": "2026-11-17",
                "level": 280,
                "experience": 900_000_000_000_000,
                "experienceRate": 96.000,
                "recordStatus": "available",
            },
            {
                "date": "2026-11-18",
                "level": 281,
                "experience": 2_500_000_000_000,
                "experienceRate": 0.144,
                "recordStatus": "available",
            },
        ]

        result = build_server_growth_metrics(
            {"level": 281, "experienceRate": 0.144},
            records,
            reference_date=today,
            period_days=2,
        )

        summary = result["periodSummary"]
        self.assertEqual(summary["experienceGainSum"], 40_000_000_000_000)
        self.assertEqual(summary["experienceGainSumLowerBound"], 39_990_234_476_724)
        self.assertEqual(summary["experienceGainSumUpperBound"], 40_009_765_726_727)
        self.assertIsNone(summary["observedExperienceSum"])
        self.assertEqual(summary["reconstructedLevelUpExperienceSum"], 40_000_000_000_000)
        self.assertEqual(summary["reconstructedLevelUpIntervals"], 1)
        self.assertEqual(summary["validGrowthIntervals"], 1)
        self.assertEqual(summary["averageDailyExperience"], 40_000_000_000_000)
        self.assertEqual(result["metrics"]["calculatedChangeDays"], 1)
        self.assertEqual(result["metrics"]["observedChangeDays"], 0)
        self.assertEqual(result["metrics"]["averageDailyGrowth"], 40_000_000_000_000)

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
