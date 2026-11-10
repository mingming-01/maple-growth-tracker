import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tracker import create_app
from tracker.runtime import get_runtime_state, initialize_snapshot_db, load_api_snapshot


class CharacterCombatPowerProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "FLASK_SECRET_KEY": "test-combat-power-secret-key-32-chars",
            "GROWTH_DATABASE_URL": "",
        })
        with self.app.app_context():
            state = get_runtime_state()
            state.snapshot_db_path = str(Path(self.temp_dir.name) / "snapshots.sqlite3")
            state.cache.clear()
            initialize_snapshot_db()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            get_runtime_state().cache.clear()
        self.temp_dir.cleanup()

    @patch("tracker.controller.character_controller.get_current_combat_power")
    @patch("tracker.controller.character_controller.get_character_rankings")
    @patch("tracker.controller.character_controller.resolve_character")
    def test_main_profile_loads_current_power_and_tracks_new_best(
        self, resolve_character, get_rankings, get_current_power
    ):
        basic = {
            "character_name": "밍득",
            "character_image": None,
            "world_name": "크로아",
            "character_class": "아크메이지(불,독)",
            "character_guild_name": "테스트",
            "character_level": 299,
            "character_exp": 123456789,
            "character_exp_rate": "86.595",
        }
        resolve_character.return_value = ("sample-ocid", basic, Mock(status_code=200))
        get_rankings.return_value = {
            "ranking": 1,
            "worldRanking": 2,
            "jobWorldRanking": 3,
            "jobRanking": 4,
            "rankingDataStatus": "available",
            "rankingDate": "2026-11-10",
            "rankingApiStatuses": {},
            "rankingApiDiagnostics": {},
            "rankingWarnings": [],
        }
        get_current_power.side_effect = ["887338916", "800000000"]

        first = self.client.get("/api/character?name=밍득").get_json()
        self.assertEqual(first["currentCombatPower"], "887338916")
        self.assertEqual(first["bestCombatPower"], 887338916)
        self.assertTrue(first["bestCombatPowerObservedAt"])

        refreshed = self.client.get(
            "/api/character?name=밍득&refresh=1"
        ).get_json()
        self.assertEqual(refreshed["currentCombatPower"], "800000000")
        self.assertEqual(refreshed["bestCombatPower"], 887338916)
        self.assertEqual(
            refreshed["bestCombatPowerObservedAt"],
            first["bestCombatPowerObservedAt"],
        )
        self.assertEqual(get_current_power.call_count, 2)
        get_current_power.assert_any_call("sample-ocid", force_refresh=False)
        get_current_power.assert_any_call("sample-ocid", force_refresh=True)

        with self.app.app_context():
            saved_best, _ = load_api_snapshot("combat-power-best:sample-ocid")
        self.assertEqual(saved_best["value"], 887338916)


if __name__ == "__main__":
    unittest.main()
