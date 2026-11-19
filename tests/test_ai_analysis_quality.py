import unittest

from tracker.services.ai_analysis_service import (
    _apply_deterministic_growth_forecast,
    _build_growth_report_prompt,
    _filter_growth_history_to_selected_period,
    _deterministic_growth_forecast,
    _error_result,
    _build_deterministic_growth_report,
    _validate_growth_report_facts,
    _growth_report_fact_error,
    _format_experience_korean,
    _build_growth_report_cache_key,
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
        self.assertIn("예상하기 어려워요", _deterministic_growth_forecast(
            {"level": 298}, {"prediction": {"nextLevel": 299, "estimatedDate": "not-a-date"}}
        ))

    def test_growth_forecast_keeps_ai_interpretation_and_adds_server_forecast(self):
        report = (
            "[성장 패턴] 최근 기록이 확인됩니다.\n"
            "[성장 변화] 성장량이 확인됩니다.\n"
            "[레벨업 분석] 현재 레벨을 유지하고 있습니다.\n"
            "[성장 전망] 1.78×10¹³ 경험치로 조건부 전망입니다.\n"
            "[AI 코멘트] 기록을 계속 확인해 주세요."
        )
        sanitized = sanitize_ai_text(report)
        result = _apply_deterministic_growth_forecast(
            sanitized, {"level": 298},
            {"prediction": {"nextLevel": 299, "estimatedDate": "2026-11-19"}},
        )
        self.assertNotIn("1.78×10¹³", result)
        self.assertIn("조건부 전망입니다.", result)
        self.assertIn("11월 19일쯤 299레벨", result)
        self.assertTrue(validate_growth_report(result))

    def test_experience_formatter_uses_compact_trillion_units(self):
        self.assertEqual(_format_experience_korean(99183417210742), "99.2조")
        self.assertEqual(_format_experience_korean(16530569535123.67), "16.5조")
        self.assertEqual(_format_experience_korean(16776913065046.14), "16.8조")
        self.assertEqual(_format_experience_korean(250000000), "2.5억")
        self.assertEqual(_format_experience_korean(999999999999.99), "1.0조")

    def test_deterministic_report_uses_server_values_for_units_dates_and_progress(self):
        character = {"level": 299}
        metrics = {
            "levelProgress": {"currentRate": 67.4, "remainingRate": 32.6},
            "levelUps": [{
                "date": "2026-11-18",
                "previousLevel": 298,
                "currentLevel": 299,
            }],
            "prediction": None,
        }
        insights = {
            "recentPeriod": {
                "startDate": "2026-11-13",
                "endDate": "2026-11-19",
                "validGrowthIntervals": 6,
                "levelUpIntervals": 1,
                "observedExperienceSum": 99183417210742,
                "averageDailyExperience": 16530569535123.67,
            },
            "previousPeriod": {
                "startDate": "2026-11-06",
                "endDate": "2026-11-12",
                "averageDailyExperience": 16776913065046.14,
            },
            "weekOverWeek": {
                "status": "available",
                "direction": "decrease",
                "averageDailyGrowthChangePercent": -1.5,
            },
        }

        report = _build_deterministic_growth_report(
            character,
            metrics,
            insights,
            {"periodDays": 7},
            "최근 흐름은 직전 기간과 큰 차이가 없지만, 추세를 더 지켜보는 것이 좋아요.",
        )

        self.assertIn("99.2조", report)
        self.assertIn("16.5조", report)
        self.assertIn("11월 6일~12일", report)
        self.assertIn("11월 13일~19일", report)
        self.assertIn("11월 18일에 298레벨에서 299레벨", report)
        self.assertIn("67.4%", report)
        self.assertIn("32.6% 남았어요", report)
        self.assertNotIn("99경", report)
        self.assertNotIn("16경", report)
        self.assertNotIn("1,834억", report)

    def test_growth_report_cache_key_includes_character_specific_data(self):
        prompt = "comment-only prompt"
        first = {"character": {"name": "밍득"}, "metrics": {"average": 100}}
        second = {"character": {"name": "다른 캐릭터"}, "metrics": {"average": 100}}

        self.assertNotEqual(
            _build_growth_report_cache_key(prompt, first),
            _build_growth_report_cache_key(prompt, second),
        )

    def test_ai_history_excludes_snapshot_before_selected_period(self):
        history = [
            {"date": "2026-11-12", "experienceChange": 100},
            {"date": "2026-11-13", "experienceChange": 200},
            {"date": "2026-11-19", "experienceChange": 300},
        ]
        filtered = _filter_growth_history_to_selected_period(
            history,
            {"periodSummary": {"startDate": "2026-11-13", "endDate": "2026-11-19"}},
        )

        self.assertEqual([item["date"] for item in filtered], ["2026-11-13", "2026-11-19"])

    def test_growth_report_prompt_gives_ai_all_five_sections_and_server_facts(self):
        source = self.make_source_data(7)
        source["history"] = [{"date": "2026-11-18", "level": 299, "experienceChange": 16530569535123}]
        prompt = _build_growth_report_prompt(source)

        for section in ("[성장 패턴]", "[성장 변화]", "[레벨업 분석]", "[성장 전망]", "[AI 코멘트]"):
            self.assertIn(section, prompt)
        self.assertIn("16530569535123", prompt)
        self.assertIn("친근하고 담백한 해요체", prompt)
        self.assertNotIn("숫자, 숫자, 날짜", prompt)

    def test_growth_report_fact_validator_accepts_server_numbers_and_dates(self):
        source = {
            "metrics": {
                "averageDailyGrowth": 16530569535123,
                "levelProgress": {"currentRate": 67.4, "remainingRate": 32.6},
                "levelUps": [{"date": "2026-11-18", "previousLevel": 298, "currentLevel": 299}],
            },
            "selectedPeriod": {"periodDays": 7},
        }
        report = (
            "[성장 패턴] 최근 7일 동안 성장 기록이 이어졌어요.\n"
            "[성장 변화] 하루 평균은 16.5조예요.\n"
            "[레벨업 분석] 11월 18일에 298레벨에서 299레벨로 올랐어요. 현재 진행률은 67.4%예요.\n"
            "[성장 전망] 기록을 바탕으로 다음 레벨을 예상해요.\n"
            "[AI 코멘트] 최근 흐름을 조금 더 지켜보면 좋겠어요."
        )
        self.assertTrue(_validate_growth_report_facts(report, source))
        wrong_unit = report.replace("16.5조", "16.5경")
        self.assertFalse(_validate_growth_report_facts(wrong_unit, source))

    def test_growth_report_fact_validator_rejects_invented_number_and_date(self):
        source = {
            "metrics": {"averageDailyGrowth": 16530569535123},
            "history": [{"date": "2026-11-18"}],
        }
        report = (
            "[성장 패턴] 최근 기록이 있어요.\n"
            "[성장 변화] 하루 평균은 19.0조예요.\n"
            "[레벨업 분석] 11월 19일에 레벨업했어요.\n"
            "[성장 전망] 기록을 더 쌓아야 해요.\n"
            "[AI 코멘트] 지금 흐름을 이어가면 좋겠어요."
        )
        self.assertFalse(_validate_growth_report_facts(report, source))
        self.assertEqual(_growth_report_fact_error(report, source), "unsupported_date")

    def test_growth_report_fact_validator_allows_natural_prose_but_categorizes_unknown_number(self):
        source = {"metrics": {"averageDailyGrowth": 1000}, "history": [{"date": "2026-11-18"}]}
        prose = "기록을 보면 최근 성장 흐름이 안정적이며, 꾸준한 플레이가 이어졌습니다."
        self.assertEqual(_growth_report_fact_error(prose, source), True)
        self.assertEqual(_growth_report_fact_error(prose + " 9999", source), "unsupported_number")

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
