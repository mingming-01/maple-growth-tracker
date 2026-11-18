"""Nexon API 오류 시 기존 DB 캐릭터 스냅샷 폴백 테스트."""
from unittest import TestCase
from unittest.mock import Mock, patch

from flask import Flask, jsonify

from tracker.controller import character_controller


class CharacterSearchStaleCacheFallbackTests(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(character_controller.character_bp)

    def test_400_upstream_error_returns_existing_snapshot(self):
        snapshot = {
            "characterName": "밍득",
            "worldName": "크로아",
            "level": 297,
            "dataStatus": "stale",
        }
        upstream_response = Mock(status_code=400)

        with patch.multiple(
            character_controller,
            get_cache=Mock(return_value=None),
            api_request_limit_response=Mock(return_value=None),
            resolve_character=Mock(return_value=(None, None, upstream_response)),
            stale_snapshot_response=Mock(
                return_value=(jsonify(snapshot), 200)
            ),
        ) as mocks:
            response = self.app.test_client().get("/api/character?name=밍득")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["characterName"], "밍득")
        self.assertEqual(response.get_json()["dataStatus"], "stale")
        mocks["stale_snapshot_response"].assert_called_once()

    def test_400_without_snapshot_preserves_upstream_status(self):
        upstream_response = Mock(status_code=400)

        with patch.multiple(
            character_controller,
            get_cache=Mock(return_value=None),
            api_request_limit_response=Mock(return_value=None),
            resolve_character=Mock(return_value=(None, None, upstream_response)),
            stale_snapshot_response=Mock(
                return_value=(jsonify({"error": "not found"}), 503)
            ),
        ):
            response = self.app.test_client().get("/api/character?name=없는캐릭터")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "캐릭터 정보를 찾을 수 없거나 조회할 수 없습니다.",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
