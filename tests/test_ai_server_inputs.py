"""AI 라우트가 클라이언트 계산값 대신 서버 저장 기록을 사용하는지 검증한다."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from tracker import create_app
from tracker.controller import ai_controller
from tracker.runtime import KOREA_TIMEZONE, get_runtime_state


class FakeGrowthStorage:
    def __init__(self, records_by_ocid):
        self.records_by_ocid = records_by_ocid
        self.calls = []

    def get_records(self, ocid, start_date, end_date):
        self.calls.append((ocid, start_date, end_date))
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
            captured.update(history=history, metrics=metrics, insights=insights, context=context)
            return {"analysis": "테스트 분석"}

        with (
            patch.object(
                ai_controller,
                "resolve_character",
                return_value=("ocid-one", self.make_basic("테스트캐릭터"), Mock(status_code=200)),
            ) as resolve,
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
        self.assertEqual(
            captured["insights"]["recentPeriod"]["observedExperienceSum"],
            captured["context"]["periodSummary"]["observedExperienceSum"],
        )
        resolve.assert_called_once_with(
            "테스트캐릭터",
            timeout_override=(1.5, 2.5),
            max_attempts_override=1,
        )

    def test_api_ai_route_preserves_exact_same_level_exp_delta_on_level_up_date(self):
        captured = {}
        records = [
            {
                "date": (self.today - timedelta(days=2)).isoformat(),
                "level": 298, "experience": 1129263590513928,
                "experienceRate": 99.226, "recordStatus": "available",
            },
            {
                "date": (self.today - timedelta(days=1)).isoformat(),
                "level": 298, "experience": 1156066685461973,
                "experienceRate": 0.355, "recordStatus": "available",
            },
            {
                "date": self.today.isoformat(),
                "level": 299, "experience": 17096549681346,
                "experienceRate": 0.984, "recordStatus": "available",
            },
        ]
        storage = FakeGrowthStorage({"ocid-one": records})

        def generate(character, history, metrics, insights, context, force_refresh):
            captured.update(
                history=history, metrics=metrics, insights=insights, context=context
            )
            return {"analysis": "실제 AI 출력 대체 검증"}

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
                json={"analysisContext": {"periodDays": 7}},
            )

        self.assertEqual(response.status_code, 200)
        reset_day = captured["history"][-2]
        catch_up_day = captured["history"][-1]
        self.assertTrue(reset_day["levelUp"])
        self.assertEqual(reset_day["experienceChange"], 26803094948045)
        self.assertTrue(catch_up_day["levelUpCatchUp"])
        self.assertFalse(catch_up_day["levelUp"])
        self.assertIsNone(catch_up_day["experienceChange"])
        self.assertEqual(captured["metrics"]["observedChangeDays"], 1)
        self.assertEqual(captured["metrics"]["averageDailyGrowth"], 26803094948045)
        self.assertEqual(
            captured["metrics"]["levelUps"],
            [{
                "date": (self.today - timedelta(days=1)).isoformat(),
                "previousLevel": 298,
                "currentLevel": 299,
            }],
        )
        self.assertEqual(captured["insights"]["recentPeriod"]["validGrowthIntervals"], 1)
        self.assertEqual(
            captured["insights"]["recentPeriod"]["observedExperienceSum"],
            26803094948045,
        )
        self.assertEqual(captured["insights"]["recentPeriod"]["levelUpIntervals"], 1)
        self.assertEqual(captured["context"]["periodSummary"]["validGrowthIntervals"], 1)

    def test_api_route_runs_real_ai_report_pipeline_with_saved_level_up_growth(self):
        event_date = self.today - timedelta(days=1)
        previous_date = self.today - timedelta(days=2)
        previous_experience = 1129263590513928
        reset_experience = 1156066685461973
        storage = FakeGrowthStorage({"ocid-one": [
            {
                "date": previous_date.isoformat(),
                "level": 298,
                "experience": previous_experience,
                "experienceRate": 99.226,
                "recordStatus": "available",
            },
            {
                "date": event_date.isoformat(),
                "level": 298,
                "experience": reset_experience,
                "experienceRate": 0.355,
                "recordStatus": "available",
            },
            {
                "date": self.today.isoformat(),
                "level": 299,
                "experience": 17096549681346,
                "experienceRate": 0.984,
                "recordStatus": "available",
            },
        ]})
        report = (
            "[성장 패턴] 확인된 성장 기록을 바탕으로 최근 변화를 살펴봤어요.\n"
            "[성장 변화] 같은 레벨의 원본 경험치 차이를 기준으로 일일 증가량을 계산했어요.\n"
            f"[레벨업 분석] {event_date.month}월 {event_date.day}일에 298레벨에서 299레벨로 올라갔어요.\n"
            "[성장 전망] 현재 기록만으로는 다음 레벨업 날짜를 확정하기 어려워요.\n"
            "[AI 코멘트] 레벨업 뒤에는 새 레벨의 경험치 진행률을 기준으로 살펴보세요."
        )

        with self.app.app_context():
            state = get_runtime_state()
            state.gemini_api_key = "test-gemini-key"
            state.openrouter_api_key = "test-openrouter-key"
            state.ai_response_cache.clear()

        with (
            patch.object(
                ai_controller,
                "resolve_character",
                return_value=("ocid-one", {
                    **self.make_basic("테스트캐릭터"),
                    "character_level": 299,
                    "character_exp": 17096549681346,
                    "character_exp_rate": 0.984,
                }, Mock(status_code=200)),
            ),
            patch.object(ai_controller, "get_growth_history_service", return_value=storage),
            patch(
                "tracker.services.ai_analysis_service._gemini_cooldown_remaining",
                return_value=0,
            ),
            patch(
                "tracker.services.ai_analysis_service.request_gemini",
                side_effect=__import__("tracker.integrations.ai_provider", fromlist=["ProviderError"]).ProviderError(
                    "Gemini unavailable", "provider_unavailable"
                ),
            ) as gemini_request,
            patch(
                "tracker.services.ai_analysis_service.request_openrouter",
                return_value=report,
            ) as openrouter_request,
        ):
            response = self.client.post(
                "/api/ai-analysis?name=테스트캐릭터",
                json={
                    "forceRefresh": True,
                    "analysisContext": {"periodDays": 7},
                },
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertFalse(payload["cacheHit"])
        self.assertIn("[성장 패턴]", payload["analysis"])
        self.assertIn("26.8조", payload["analysis"])
        self.assertIn("[AI 코멘트]", payload["analysis"])
        self.assertIn(
            f"{event_date.month}월 {event_date.day}일에 298레벨에서 299레벨로 올라갔어요.",
            payload["analysis"],
        )
        self.assertIn("다음 레벨업 날짜를 예상하기 어려워요.", payload["analysis"])

        gemini_request.assert_called_once()
        openrouter_request.assert_called_once()
        prompt = openrouter_request.call_args.args[0]
        self.assertIn("레벨업 전환이 확인됨", prompt)
        self.assertNotIn('"experienceChange"', prompt)
        self.assertNotIn('"date":', prompt)
        self.assertNotIn(str(reset_experience), prompt)
        self.assertNotIn(
            str(17096549681346 - reset_experience),
            prompt,
        )

    def test_analysis_excludes_unverified_legacy_ranks_before_ai_generation(self):
        captured = {}
        records = [
            {
                "date": (self.today - timedelta(days=1)).isoformat(),
                "level": 280,
                "experience": 1000,
                "ranking": 200,
                "rankingScope": "overall",
                "rankingSourceDate": None,
                "recordStatus": "available",
            },
            {
                "date": self.today.isoformat(),
                "level": 280,
                "experience": 1150,
                "ranking": 190,
                "rankingScope": "overall",
                "rankingSourceDate": (self.today - timedelta(days=1)).isoformat(),
                "recordStatus": "available",
            },
        ]
        storage = FakeGrowthStorage({"ocid-one": records})

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
            response = self.client.post("/api/ai-analysis?name=테스트캐릭터", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["ranking"] for item in captured["history"]], [None, None])
        self.assertIsNone(captured["metrics"]["rankingChange"])

    def test_ai_analysis_uses_server_period_boundaries_for_30_and_90_days(self):
        for period_days in (30, 90):
            with self.subTest(period_days=period_days):
                captured = {}
                storage = FakeGrowthStorage({"ocid-one": self.make_records(1000)})

                def generate(character, history, metrics, insights, context, force_refresh):
                    captured.update(history=history, metrics=metrics, insights=insights, context=context)
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
                        json={"analysisContext": {"periodDays": period_days}},
                    )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(captured["context"]["periodDays"], period_days)
                summary = captured["context"]["periodSummary"]
                self.assertEqual(summary["expectedSnapshots"], period_days)
                self.assertEqual(
                    summary["startDate"],
                    (self.today - timedelta(days=period_days - 1)).isoformat(),
                )
                self.assertEqual(summary["endDate"], self.today.isoformat())
                # DB 조회는 선택 기간 첫날의 레벨업 전환을 비교할 직전 스냅샷도 포함한다.
                self.assertEqual(storage.calls[0][1], self.today - timedelta(days=period_days))
                self.assertEqual(storage.calls[0][2], self.today)

    def test_analysis_includes_previous_day_to_detect_period_start_level_up(self):
        captured = {}
        period_start = self.today - timedelta(days=6)
        records = [{
            "date": (period_start - timedelta(days=1)).isoformat(),
            "level": 280,
            "experience": 9900,
            "ranking": 200,
            "recordStatus": "available",
        }]
        for offset in range(7):
            record_date = period_start + timedelta(days=offset)
            records.append({
                "date": record_date.isoformat(),
                "level": 281,
                "experience": 100 + offset * 100,
                "ranking": 190 - offset,
                "recordStatus": "available",
            })
        storage = FakeGrowthStorage({"ocid-one": records})
        snapshot = {
            "ocid": "ocid-one",
            "characterName": "테스트캐릭터",
            "worldName": "테스트월드",
            "job": "테스트직업",
            "level": 281,
            "experience": 700,
            "experienceRate": 42.5,
        }

        def generate(character, history, metrics, insights, context, force_refresh):
            captured.update(history=history, metrics=metrics)
            return {"analysis": "테스트 분석"}

        with (
            patch.object(
                ai_controller,
                "load_api_snapshot",
                return_value=(snapshot, datetime.now().astimezone().isoformat()),
            ),
            patch.object(ai_controller, "get_growth_history_service", return_value=storage),
            patch.object(ai_controller, "generate_ai_analysis", side_effect=generate),
        ):
            response = self.client.post("/api/ai-analysis?name=테스트캐릭터", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["metrics"]["levelUps"][0]["date"], period_start.isoformat())
        self.assertEqual(captured["metrics"]["levelUps"][0]["previousLevel"], 280)
        self.assertEqual(captured["metrics"]["levelUps"][0]["currentLevel"], 281)
        self.assertEqual(captured["history"][0]["date"], (period_start - timedelta(days=1)).isoformat())


    def test_comparison_rebuilds_both_subjects_from_server_records(self):
        captured = {}
        storage = FakeGrowthStorage({
            "ocid-one": self.make_records(1000),
            "ocid-two": self.make_records(2000),
        })

        def resolve(name, **_kwargs):
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


    def test_ai_route_reuses_recent_profile_and_reads_growth_records_once(self):
        captured = {}
        storage = FakeGrowthStorage({"ocid-one": self.make_records(1000)})
        snapshot = {
            "ocid": "ocid-one",
            "characterName": "테스트캐릭터",
            "worldName": "테스트월드",
            "job": "테스트직업",
            "level": 280,
            "experience": 1500,
            "experienceRate": 42.5,
        }

        def generate(character, history, metrics, insights, context, force_refresh):
            captured["character"] = character
            captured["history"] = history
            return {"analysis": "테스트 분석"}

        with (
            patch.object(
                ai_controller,
                "load_api_snapshot",
                return_value=(snapshot, datetime.now().astimezone().isoformat()),
            ),
            patch.object(ai_controller, "resolve_character", side_effect=AssertionError("fresh profile should be reused")),
            patch.object(ai_controller, "get_growth_history_service", return_value=storage),
            patch.object(ai_controller, "generate_ai_analysis", side_effect=generate),
        ):
            response = self.client.post("/api/ai-analysis?name=테스트캐릭터", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["character"]["ocid"], "ocid-one")
        self.assertEqual(captured["character"]["job"], "테스트직업")
        self.assertEqual(len(storage.calls), 1)
        self.assertEqual(storage.calls[0][1], self.today - timedelta(days=14))
        self.assertEqual(storage.calls[0][2], self.today)


if __name__ == "__main__":
    unittest.main()
