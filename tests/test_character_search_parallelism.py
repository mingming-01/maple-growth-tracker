"""캐릭터 검색의 독립적인 Nexon 조회 작업 병렬 실행 테스트."""
from threading import Barrier
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from flask import Flask, current_app, has_app_context

from tracker.controller import character_controller


class CharacterSearchParallelismTests(TestCase):
    def test_rankings_and_combat_power_are_started_concurrently(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["CUSTOM_TEST_SETTING"] = "preserved-in-worker"
        app.register_blueprint(character_controller.character_bp)

        rendezvous = Barrier(2)
        basic = {
            "character_name": "밍득크로아",
            "character_class": "아크메이지(썬,콜)",
            "world_name": "크로아",
            "character_level": 297,
            "character_exp": 123456789,
            "character_exp_rate": 45.6,
            "character_image": None,
            "character_guild_name": "테스트길드",
        }
        rankings = {
            "ranking": 100,
            "worldRanking": 50,
            "jobWorldRanking": 10,
            "jobRanking": 20,
            "rankingDataStatus": "available",
            "rankingDate": "2026-11-10",
            "rankingApiStatuses": {},
            "rankingApiDiagnostics": {},
            "rankingWarnings": [],
        }

        def wait_for_both_tasks():
            # 두 작업이 모두 시작되지 않으면 timeout으로 테스트가 실패한다.
            rendezvous.wait(timeout=3)

        def fetch_rankings(**kwargs):
            wait_for_both_tasks()
            self.assertEqual(kwargs["ocid"], "sample-ocid")
            self.assertEqual(kwargs["world_name"], "크로아")
            return rankings

        def fetch_combat_power(ocid, force_refresh=False):
            self.assertTrue(has_app_context())
            self.assertIs(current_app._get_current_object(), app)
            self.assertEqual(
                current_app.config["CUSTOM_TEST_SETTING"],
                "preserved-in-worker",
            )
            self.assertEqual(ocid, "sample-ocid")
            self.assertFalse(force_refresh)
            wait_for_both_tasks()
            return "123456789"

        with patch.object(character_controller, "observe_metric") as observe_metric:
            with patch.multiple(
                character_controller,
                get_cache=Mock(return_value=None),
                api_request_limit_response=Mock(return_value=None),
                resolve_character=Mock(
                    return_value=("sample-ocid", basic, Mock(status_code=200))
                ),
                get_character_rankings=Mock(side_effect=fetch_rankings),
                get_current_combat_power=Mock(side_effect=fetch_combat_power),
                record_best_combat_power=Mock(
                    return_value={
                        "value": 123456789,
                        "observedAt": "2026-11-10T16:00:00+09:00",
                        "presetNumbers": None,
                    }
                ),
                delete_cache=Mock(),
                load_api_snapshot=Mock(return_value=(None, None)),
                save_api_snapshot=Mock(return_value="2026-11-10T16:00:00+09:00"),
                set_cache=Mock(),
            ):
                response = app.test_client().get(
                    "/api/character?name=%EB%B0%8D%EB%93%9D%ED%81%AC%EB%A1%9C%EC%95%84"
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["dataStatus"], "current")
        self.assertEqual(payload["ranking"], 100)
        self.assertEqual(payload["currentCombatPower"], "123456789")
        self.assertEqual(payload["bestCombatPower"], 123456789)

        component_calls = {
            call.kwargs.get("component")
            for call in observe_metric.call_args_list
            if call.args and call.args[0] == "character.search_component_ms"
        }
        self.assertEqual(component_calls, {"rankings", "combat_power"})
        observe_metric.assert_any_call(
            "character.search_parallel_ms",
            ANY,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
