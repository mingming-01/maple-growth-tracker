import unittest
from tracker.services.ai_text_service import sanitize_ai_text, validate_growth_report


class SanitizeAITextTests(unittest.TestCase):
    def test_decimal_percentage_is_not_rewritten_as_prediction_date(self):
        result = sanitize_ai_text(
            "최근 성장률은 11.17% 증가했습니다.",
            expected_date="2026-11-17",
        )
        self.assertIn("11.17%", result)
        self.assertNotIn("11월 17일%", result)

    def test_prediction_date_is_normalized_without_changing_percentages(self):
        result = sanitize_ai_text(
            "다음 레벨 예상일은 2026-11-17이며 성장률은 8.25%입니다.",
            expected_date="2026-11-17",
        )
        self.assertIn("11월 17일", result)
        self.assertIn("8.25%", result)


    def test_prediction_date_normalization_preserves_historical_event_dates(self):
        result = sanitize_ai_text(
            "최고 성장일은 2026-10-19이고 298레벨 달성일은 10월 25일입니다. "
            "다음 레벨 예상일은 2026-11-19입니다.",
            expected_date="2026-11-19",
        )

        self.assertIn("2026-10-19", result)
        self.assertIn("10월 25일", result)
        self.assertIn("11월 19일", result)

    def test_unrelated_iso_dates_are_not_replaced_by_prediction_date(self):
        result = sanitize_ai_text(
            "관측 기록은 2026-10-25이며 다음 레벨 예상일은 2026-11-19입니다.",
            expected_date="2026-11-19",
        )

        self.assertIn("2026-10-25", result)
        self.assertIn("11월 19일", result)


    def test_technical_growth_terms_are_rewritten_for_players(self):
        result = sanitize_ai_text(
            "최근 관측 구간의 표본이 적고 결측 날짜가 많습니다."
        )

        self.assertNotIn("관측", result)
        self.assertNotIn("표본", result)
        self.assertNotIn("결측", result)
        self.assertIn("최근 기간", result)
        self.assertIn("기록된 날짜", result)
        self.assertIn("기록이 없는 날짜", result)

    def test_growth_report_rejects_chinese_characters(self):
        report = (
            "[성장 패턴] 最近 성장 기록입니다.\n"
            "[성장 변화] 변화가 확인됩니다.\n"
            "[레벨업 분석] 기록이 부족합니다.\n"
            "[성장 전망] 예측하기 어렵습니다.\n"
            "[AI 코멘트] 확인이 필요합니다."
        )
        self.assertFalse(validate_growth_report(report))

    def test_growth_report_accepts_korean_required_sections(self):
        report = (
            "[성장 패턴] 최근 성장 기록입니다.\n"
            "[성장 변화] 변화가 확인됩니다.\n"
            "[레벨업 분석] 기록이 부족합니다.\n"
            "[성장 전망] 예측하기 어렵습니다.\n"
            "[AI 코멘트] 확인이 필요합니다."
        )
        self.assertTrue(validate_growth_report(report))

    def test_growth_report_rejects_missing_sections(self):
        report = "[성장 패턴] 분석 결과입니다."
        self.assertFalse(validate_growth_report(report))



if __name__ == "__main__":
    unittest.main()
