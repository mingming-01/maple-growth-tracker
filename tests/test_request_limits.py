"""Tests for AI request budgets and administrator login lockout."""
import unittest
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from tracker import create_app
from tracker.controller import ai_controller
from tracker.integrations import nexon_api
from tracker.runtime import get_runtime_state
from tracker.services.request_limits import (
    admin_login_lockout_remaining,
    clear_admin_login_failures,
    consume_ai_request,
    record_admin_login_failure,
)


class RequestLimitTests(unittest.TestCase):
    def make_app(self, **overrides):
        config = {
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "NEXON_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "AI_MAX_REQUESTS_PER_MINUTE": 5,
            "AI_MAX_REQUESTS_PER_DAY_PER_IP": 20,
            "AI_MAX_REQUESTS_PER_DAY_GLOBAL": 100,
            "ADMIN_LOGIN_MAX_ATTEMPTS": 2,
            "ADMIN_LOGIN_WINDOW_SECONDS": 900,
            "ADMIN_LOGIN_LOCKOUT_SECONDS": 300,
        }
        config.update(overrides)
        return create_app(config)

    def test_ai_minute_limit_is_enforced_per_client(self):
        app = self.make_app(AI_MAX_REQUESTS_PER_MINUTE=1)
        with app.app_context():
            self.assertTrue(consume_ai_request("192.0.2.1")[0])
            allowed, retry_after, reason = consume_ai_request("192.0.2.1")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)
        self.assertEqual(reason, "minute")

    def test_ai_global_daily_budget_is_enforced_across_clients(self):
        app = self.make_app(
            AI_MAX_REQUESTS_PER_MINUTE=10,
            AI_MAX_REQUESTS_PER_DAY_PER_IP=10,
            AI_MAX_REQUESTS_PER_DAY_GLOBAL=1,
        )
        with app.app_context():
            self.assertTrue(consume_ai_request("192.0.2.1")[0])
            allowed, retry_after, reason = consume_ai_request("192.0.2.2")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)
        self.assertEqual(reason, "global_daily")

    def test_ai_route_returns_429_before_calling_nexon(self):
        app = self.make_app(AI_MAX_REQUESTS_PER_MINUTE=1)
        with app.app_context():
            self.assertTrue(consume_ai_request("127.0.0.1")[0])
        client = app.test_client()
        with patch.object(ai_controller, "get_character", side_effect=AssertionError("must not call Nexon")):
            response = client.get("/api/ai-analysis?name=테스트캐릭터")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_admin_login_is_locked_after_repeated_failures(self):
        app = self.make_app(
            ADMIN_USERNAME="admin",
            ADMIN_PASSWORD_HASH=generate_password_hash("correct-password"),
        )
        client = app.test_client()
        with client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"

        first = client.post("/admin/login", data={
            "csrf_token": "test-csrf",
            "username": "admin",
            "password": "wrong",
        })
        second = client.post("/admin/login", data={
            "csrf_token": "test-csrf",
            "username": "admin",
            "password": "wrong",
        })
        third = client.post("/admin/login", data={
            "csrf_token": "test-csrf",
            "username": "admin",
            "password": "correct-password",
        })

        self.assertEqual(first.status_code, 200)
        self.assertIn("로그인 실패 횟수를 초과", second.get_data(as_text=True))
        self.assertEqual(third.status_code, 200)
        self.assertNotIn("관리자 로그", third.get_data(as_text=True))
        with app.test_request_context():
            self.assertGreater(admin_login_lockout_remaining("127.0.0.1"), 0)

    def test_production_ignores_plaintext_admin_password(self):
        app = self.make_app(
            IS_PRODUCTION=True,
            ADMIN_USERNAME="admin",
            ADMIN_PASSWORD="legacy-plaintext",
            ADMIN_PASSWORD_HASH="",
        )
        client = app.test_client()
        with client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"
        response = client.post("/admin/login", data={
            "csrf_token": "test-csrf",
            "username": "admin",
            "password": "legacy-plaintext",
        })
        self.assertIn("ADMIN_PASSWORD_HASH", response.get_data(as_text=True))
        self.assertNotIn("admin_authenticated", dict(client.session_transaction()))

    def test_admin_lockout_can_be_cleared_after_successful_authentication(self):
        app = self.make_app()
        with app.app_context():
            record_admin_login_failure("192.0.2.5")
            record_admin_login_failure("192.0.2.5")
            self.assertGreater(admin_login_lockout_remaining("192.0.2.5"), 0)
            clear_admin_login_failures("192.0.2.5")
            self.assertEqual(admin_login_lockout_remaining("192.0.2.5"), 0)

    def test_all_nexon_requests_receive_the_shared_throttle_callback(self):
        app = self.make_app(NEXON_API_MIN_INTERVAL=0)
        response = Mock(status_code=200)
        with app.app_context(), patch.object(
            nexon_api, "request_with_retries", return_value=response
        ) as request:
            nexon_api.request_nexon_api("id", {"character_name": "테스트"})
            callback = request.call_args.kwargs["before_attempt"]
            self.assertTrue(callable(callback))
            callback()
            state = get_runtime_state()
            self.assertEqual(state.nexon_request_count, 1)


if __name__ == "__main__":
    unittest.main()
