"""AI 라우트가 클라이언트 계산값 대신 서버 저장 기록을 사용하는지 검증한다."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from tracker import create_app
from tracker.controller import ai_controller
from tracker.runtime import KOREA_TIMEZONE


class FakeGrowthStorage:
    def __init__(self, records_by_ocid):
        self.records_by_ocid = records_by_ocid

    def get_records(self, ocid, start_date, end_date):
        return [
            record for record in self.records_by_ocid.get(ocid, [])
            if start_date <= datetime.fromisoformat(record["date"]).date() <= end_date
        ]


class AIServerInputTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        })
        self.client = self.app.test_client()
        self.today = datetime.now(KOREA_TIMEZONE).date()

    def make_records(self, base_experience):
        return [
            {
                "date": (self.today - timedelta(days=1)).isoformat(),
                "level": 280,
                "experience": base_experience,
                "ranking": 200,
                "recordStatus": "available",
            },
            {
                "date": self.today.isoformat(),
                "level": 280,
                "experience": base_experience + 150,
                "ranking": 190,
                "recordStatus": "available",
            },
        ]

    @staticmethod
    def make_basic(name):
        return {
            "character_name": name,
            "world_name": "테스트월드",
            "character_class": "테스트직업",
            "character_level": 280,
            "character_exp": 1500,
            "character_exp_rate": 42.5,
        }

    def test_analysis_ignores_forged_client_metrics_and_history(self):
        captured = {}
        storage = FakeGrowthStorage({"ocid-one": self.make_records(1000)})

        def generate(character, history, metrics, insights, context, force_refresh):
            captured.update(history=history, metrics=metrics, context=context)
            return {"analysis": "테스트 분석"}

        with (
            patch.object(
                ai_controller,
                "resolve_character",
                return_value=("ocid-one", self.make_basic("테스트캐릭터"), Mock(status_code=200)),
            ),
            patch.object(ai_controller, "get_growth_history_service", return_value=storage),
            patch.object(ai_controller, "generate_ai_analysis", side_effect=generate),
        ):
            response = self.client.post(
                "/api/ai-analysis?name=테스트캐릭터",
                json={
                    "metrics": {"averageDailyGrowth": 999999999999999},
                    "history": [{"date": "2099-01-01", "experienceChange": 999999999999999}],
                    "analysisContext": {"periodDays": 7, "periodSummary": {"averageGrowth": 999999999999999}},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["metrics"]["averageDailyGrowth"], 150)
        self.assertEqual(len(captured["history"]), 2)
        self.assertNotEqual(captured["history"][0]["date"], "2099-01-01")
        self.assertEqual(captured["context"]["periodSummary"]["averageDailyExperience"], 150)

    def test_comparison_rebuilds_both_subjects_from_server_records(self):
        captured = {}
        storage = FakeGrowthStorage({
            "ocid-one": self.make_records(1000),
            "ocid-two": self.make_records(2000),
        })

        def resolve(name):
            return f"ocid-{name}", self.make_basic(name), Mock(status_code=200)

        def generate(primary, comparison):
            captured.update(primary=primary, comparison=comparison)
            return {"analysis": "테스트 비교"}

        with (
            patch.object(ai_controller, "resolve_character", side_effect=resolve),
            patch.object(ai_controller, "get_growth_history_service", return_value=storage),
            patch.object(ai_controller, "generate_ai_comparison", side_effect=generate),
        ):
            response = self.client.post(
                "/api/ai-comparison",
                json={
                    "primary": {
                        "character": {"characterName": "one"},
                        "metrics": {"averageDailyGrowth": 1},
                        "history": [],
                    },
                    "comparison": {
                        "character": {"characterName": "two"},
                        "metrics": {"averageDailyGrowth": 999999999},
                        "history": [],
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["primary"]["metrics"]["averageDailyGrowth"], 150)
        self.assertEqual(captured["comparison"]["metrics"]["averageDailyGrowth"], 150)
        self.assertEqual(len(captured["primary"]["history"]), 2)
        self.assertEqual(len(captured["comparison"]["history"]), 2)


if __name__ == "__main__":
    unittest.main()
