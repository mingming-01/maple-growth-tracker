"""Tests for AI request budgets and administrator login lockout."""
import unittest
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from tracker import create_app
from tracker.controller import ai_controller, character_controller
from tracker.integrations import nexon_api
from tracker.runtime import get_runtime_state
from tracker.services.request_limits import (
    admin_login_lockout_remaining,
    clear_admin_login_failures,
    consume_ai_request,
    consume_api_request,
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
        with patch.object(ai_controller, "resolve_character", side_effect=AssertionError("must not call Nexon")):
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
        with client.session_transaction() as session:
            self.assertNotIn("admin_authenticated", session)
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
        with client.session_transaction() as session:
            self.assertNotIn("admin_authenticated", session)

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


    def test_public_api_limit_is_per_client_and_returns_retry_window(self):
        app = self.make_app(
            API_REQUESTS_PER_MINUTE_PER_IP=1,
            API_REFRESHES_PER_MINUTE_PER_IP=5,
        )
        with app.app_context():
            first = consume_api_request("198.51.100.10")
            second = consume_api_request("198.51.100.10")
            other_client = consume_api_request("198.51.100.11")

        self.assertTrue(first[0])
        self.assertFalse(second[0])
        self.assertGreater(second[1], 0)
        self.assertEqual(second[2], "requests_per_minute")
        self.assertTrue(other_client[0])

    def test_force_refresh_has_a_separate_limit(self):
        app = self.make_app(
            API_REQUESTS_PER_MINUTE_PER_IP=10,
            API_REFRESHES_PER_MINUTE_PER_IP=1,
        )
        with app.app_context():
            first = consume_api_request("198.51.100.12", force_refresh=True)
            second = consume_api_request("198.51.100.12", force_refresh=True)
            normal = consume_api_request("198.51.100.12", force_refresh=False)

        self.assertTrue(first[0])
        self.assertFalse(second[0])
        self.assertEqual(second[2], "refreshes_per_minute")
        self.assertTrue(normal[0])

    def test_loopback_requests_are_not_limited_for_local_e2e_runs(self):
        app = self.make_app(API_REQUESTS_PER_MINUTE_PER_IP=1)
        with app.app_context():
            first = consume_api_request("127.0.0.1")
            second = consume_api_request("127.0.0.1")
        self.assertTrue(first[0])
        self.assertTrue(second[0])

    def test_production_api_limits_wait_for_trusted_proxy_configuration(self):
        app = self.make_app(
            IS_PRODUCTION=True,
            TRUSTED_PROXY_HOPS=0,
            API_REQUESTS_PER_MINUTE_PER_IP=1,
        )
        with app.app_context():
            first = consume_api_request("203.0.113.10")
            second = consume_api_request("203.0.113.10")
        self.assertTrue(first[0])
        self.assertTrue(second[0])

    def test_cached_character_response_is_not_counted_against_api_limit(self):
        app = self.make_app(API_REQUESTS_PER_MINUTE_PER_IP=1)
        with app.app_context():
            self.assertTrue(consume_api_request("198.51.100.14")[0])
            from tracker.runtime import set_cache, CHARACTER_CACHE_TTL
            set_cache(
                "character:캐시테스트",
                {"characterName": "캐시테스트", "level": 280},
                CHARACTER_CACHE_TTL,
            )

        client = app.test_client()
        response = client.get(
            "/api/character?name=캐시테스트",
            environ_overrides={"REMOTE_ADDR": "198.51.100.14"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["dataStatus"], "cached")

    def test_character_cache_miss_is_limited_before_external_api_call(self):
        app = self.make_app(API_REQUESTS_PER_MINUTE_PER_IP=1)
        client = app.test_client()
        not_found = Mock(status_code=404)

        with patch.object(
            character_controller,
            "resolve_character",
            return_value=(None, None, not_found),
        ) as resolve:
            first = client.get(
                "/api/character?name=첫번째",
                environ_overrides={"REMOTE_ADDR": "198.51.100.15"},
            )
            second = client.get(
                "/api/character?name=두번째",
                environ_overrides={"REMOTE_ADDR": "198.51.100.15"},
            )

        self.assertEqual(first.status_code, 404)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("Retry-After"), "60")
        self.assertEqual(second.get_json()["limitType"], "requests_per_minute")
        self.assertEqual(resolve.call_count, 1)

    def test_repeated_force_refresh_is_limited_before_external_api_call(self):
        app = self.make_app(
            API_REQUESTS_PER_MINUTE_PER_IP=10,
            API_REFRESHES_PER_MINUTE_PER_IP=1,
        )
        client = app.test_client()
        not_found = Mock(status_code=404)

        with patch.object(
            character_controller,
            "resolve_character",
            return_value=(None, None, not_found),
        ) as resolve:
            first = client.get(
                "/api/character?name=첫번째&refresh=1",
                environ_overrides={"REMOTE_ADDR": "198.51.100.16"},
            )
            second = client.get(
                "/api/character?name=두번째&refresh=1",
                environ_overrides={"REMOTE_ADDR": "198.51.100.16"},
            )

        self.assertEqual(first.status_code, 404)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.get_json()["limitType"], "refreshes_per_minute")
        self.assertEqual(resolve.call_count, 1)


    def test_nexon_throttle_does_not_hold_lock_while_sleeping(self):
        app = self.make_app(NEXON_API_MIN_INTERVAL=0.1)
        original_last_request_at = nexon_api._fallback_last_request_at
        lock_was_available_during_sleep = []

        def verify_lock_is_free(delay):
            acquired = nexon_api._fallback_rate_limit_lock.acquire(blocking=False)
            lock_was_available_during_sleep.append(acquired)
            if acquired:
                nexon_api._fallback_rate_limit_lock.release()

        try:
            nexon_api._fallback_last_request_at = 100.0
            with app.app_context(), patch.object(
                nexon_api.time, "monotonic", side_effect=[100.0, 100.11]
            ), patch.object(
                nexon_api.time, "sleep", side_effect=verify_lock_is_free
            ):
                nexon_api._throttle_nexon_request()
        finally:
            nexon_api._fallback_last_request_at = original_last_request_at

        self.assertEqual(lock_was_available_during_sleep, [True])

    def test_trusted_proxy_header_identifies_separate_clients(self):
        app = self.make_app(
            IS_PRODUCTION=True,
            TRUSTED_PROXY_HOPS=1,
            API_REQUESTS_PER_MINUTE_PER_IP=1,
        )
        client = app.test_client()
        not_found = Mock(status_code=404)

        with patch.object(
            character_controller,
            "resolve_character",
            return_value=(None, None, not_found),
        ) as resolve:
            first_client = client.get(
                "/api/character?name=첫번째",
                environ_overrides={
                    "REMOTE_ADDR": "203.0.113.1",
                    "HTTP_X_FORWARDED_FOR": "198.51.100.20",
                },
            )
            same_client = client.get(
                "/api/character?name=두번째",
                environ_overrides={
                    "REMOTE_ADDR": "203.0.113.1",
                    "HTTP_X_FORWARDED_FOR": "198.51.100.20",
                },
            )
            other_client = client.get(
                "/api/character?name=세번째",
                environ_overrides={
                    "REMOTE_ADDR": "203.0.113.1",
                    "HTTP_X_FORWARDED_FOR": "198.51.100.21",
                },
            )

        self.assertEqual(first_client.status_code, 404)
        self.assertEqual(same_client.status_code, 429)
        self.assertEqual(other_client.status_code, 404)
        self.assertEqual(resolve.call_count, 2)


if __name__ == "__main__":
    unittest.main()
