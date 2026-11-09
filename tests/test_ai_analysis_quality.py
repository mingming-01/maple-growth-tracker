import unittest

from tracker.services.ai_analysis_service import (
    _apply_deterministic_growth_forecast,
    _build_growth_report_prompt,
    _deterministic_growth_forecast,
    _error_result,
)
from tracker.services.ai_text_service import sanitize_ai_text, validate_growth_report


class AIAnalysisQualityTests(unittest.TestCase):
    def make_source_data(self, period_days):
        return {
            "character": {"name": "테스트", "level": 298, "experienceRate": 85.35},
            "metrics": {
                "averageDailyGrowth": 17074000000000,
                "latestDailyGrowth": 35820000000000,
                "prediction": {"estimatedDate": "2026-11-19", "estimatedDays": 9.56},
                "levelProgress": {
                    "currentRate": 85.35,
                    "remainingRate": 14.65,
                    "dailyProgressRate": 1.52,
                },
            },
            "growthInsights": {
                "weekOverWeek": {"status": "available", "averageDailyGrowthChangePercent": 4.4}
            },
            "selectedPeriod": {
                "periodDays": period_days,
                "periodSummary": {
                    "averageGrowth": 12000000000000,
                    "previousSummary": {"averageGrowth": 11000000000000},
                    "coveragePercent": 93.3,
                    "confirmedChangeDays": 26,
                },
            },
            "predictionDisplayDate": "11월 19일",
            "history": [],
        }

    def test_long_period_prompt_separates_period_metrics_from_seven_day_metrics(self):
        prompt = _build_growth_report_prompt(self.make_source_data(30))

        self.assertIn('"averageGrowth": 12000000000000', prompt)
        self.assertIn('"recentSevenDayPrediction"', prompt)
        self.assertNotIn('"averageDailyGrowth"', prompt)
        self.assertNotIn('"weekOverWeek"', prompt)
        self.assertIn('"remainingRate": 14.65', prompt)

    def test_growth_report_prompt_prefers_everyday_maple_language(self):
        prompt = _build_growth_report_prompt(self.make_source_data(30))

        self.assertIn("친근하고 담백한 해요체", prompt)
        self.assertIn("하루 평균 경험치", prompt)
        self.assertIn("관측 구간", prompt)
        self.assertIn("메이플스토리에서 익숙한", prompt)

    def test_ninety_day_prompt_also_omits_seven_day_comparison(self):
        prompt = _build_growth_report_prompt(self.make_source_data(90))

        self.assertIn('"periodDays": 90', prompt)
        self.assertNotIn('"weekOverWeek"', prompt)

    def test_seven_day_prompt_keeps_seven_day_metrics_and_insights(self):
        prompt = _build_growth_report_prompt(self.make_source_data(7))

        self.assertIn('"averageDailyGrowth"', prompt)
        self.assertIn('"weekOverWeek"', prompt)

    def test_gemini_quota_error_preserves_http_status_and_retry_delay(self):
        error = RuntimeError(
            "429 RESOURCE_EXHAUSTED {'details': [{'retryDelay': '30262s'}]}"
        )

        result = _error_result(error, "fallback")

        self.assertEqual(result["statusCode"], 429)
        self.assertEqual(result["retryAfterSeconds"], 30262)
        self.assertEqual(result["errorType"], "provider_quota")

    def test_non_quota_provider_error_is_gateway_error(self):
        result = _error_result(RuntimeError("upstream unavailable"), "fallback")

        self.assertEqual(result["statusCode"], 502)
        self.assertEqual(result["errorType"], "provider_error")


    def test_scientific_notation_is_formatted_as_korean_experience_unit(self):
        self.assertEqual(sanitize_ai_text("평균 약 1.78×10¹³ 경험치"), "평균 약 17.8조 경험치")
        self.assertEqual(sanitize_ai_text("평균 약 1.78e13 경험치"), "평균 약 17.8조 경험치")
        self.assertEqual(sanitize_ai_text("평균 약 17,800,000,000,000 경험치"), "평균 약 17.8조 경험치")

    def test_growth_forecast_uses_computed_level_and_date(self):
        forecast = _deterministic_growth_forecast(
            {"level": 298},
            {"prediction": {"nextLevel": 299, "estimatedDate": "2026-11-19"}},
        )
        self.assertEqual(
            forecast,
            "최근처럼 경험치를 얻는다면 11월 19일쯤 299레벨에 도달할 것으로 예상돼요. 실제 레벨업 날짜는 앞으로의 성장 속도에 따라 달라질 수 있어요.",
        )

    def test_growth_forecast_rejects_invalid_or_inconsistent_prediction(self):
        self.assertIn("예상하기 어려워요", _deterministic_growth_forecast(
            {"level": 298}, {"prediction": {"nextLevel": 300, "estimatedDate": "2026-11-19"}}
        ))
        self.assertIn("예측하기 어려워요", _deterministic_growth_forecast(
            {"level": 298}, {"prediction": {"nextLevel": 299, "estimatedDate": "not-a-date"}}
        ))

    def test_growth_forecast_section_is_replaced_before_validation(self):
        report = (
            "[성장 패턴] 최근 기록이 확인됩니다.\n"
            "[성장 변화] 성장량이 확인됩니다.\n"
            "[레벨업 분석] 현재 레벨을 유지하고 있습니다.\n"
            "[성장 전망] 1.78×10¹³ 경험치로 조건부 전망입니다.\n"
            "[AI 코멘트] 기록을 계속 확인해 주세요."
        )
        result = _apply_deterministic_growth_forecast(
            report, {"level": 298},
            {"prediction": {"nextLevel": 299, "estimatedDate": "2026-11-19"}},
        )
        self.assertNotIn("1.78×10¹³", result)
        self.assertIn("11월 19일경 299레벨", result)
        self.assertTrue(validate_growth_report(result))

    def test_report_validator_rejects_scientific_notation(self):
        report = (
            "[성장 패턴] 최근 기록이 확인됩니다.\n"
            "[성장 변화] 평균 성장량은 1.78×10¹³입니다.\n"
            "[레벨업 분석] 레벨업 기록은 없습니다.\n"
            "[성장 전망] 현재 자료로는 예상하기 어렵습니다.\n"
            "[AI 코멘트] 기록을 이어서 확인해 주세요."
        )
        self.assertFalse(validate_growth_report(report))

    def test_report_rejects_wrong_growth_term(self):
        report = (
            "[성장 패턴] 최근 기록이 확인됩니다.\n"
            "[성장 변화] 평균 경험치 17조 경보를 기록했습니다.\n"
            "[레벨업 분석] 레벨업 기록은 없습니다.\n"
            "[성장 전망] 현재 자료로는 예상하기 어렵습니다.\n"
            "[AI 코멘트] 기록을 이어서 확인해 주세요."
        )

        self.assertFalse(validate_growth_report(report))


if __name__ == "__main__":
    unittest.main()
