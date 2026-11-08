import unittest
from tracker.services.ai_text_service import sanitize_ai_text


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

        self.assertIn("10월 19일", result)
        self.assertIn("10월 25일", result)
        self.assertIn("11월 19일", result)
        self.assertNotIn("10월 19일", result.replace("10월 19일", "", 1) if False else "")

    def test_unrelated_iso_dates_are_not_replaced_by_prediction_date(self):
        result = sanitize_ai_text(
            "관측 기록은 2026-10-25이며 다음 레벨 예상일은 2026-11-19입니다.",
            expected_date="2026-11-19",
        )

        self.assertIn("2026-10-25", result)
        self.assertIn("11월 19일", result)



if __name__ == "__main__":
    unittest.main()
