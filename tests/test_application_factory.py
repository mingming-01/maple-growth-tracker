"""Flask application factory and blueprint registration tests."""
import unittest

from tracker import create_app


class ApplicationFactoryTests(unittest.TestCase):
    def test_runtime_state_is_isolated_between_app_instances(self):
        from tracker.runtime import get_cache, get_runtime_state, set_cache

        first_app = create_app({
            "TESTING": True,
            "NEXON_API_KEY": "first-app-key",
            "GROWTH_DATABASE_URL": "",
        })
        second_app = create_app({
            "TESTING": True,
            "NEXON_API_KEY": "second-app-key",
            "GROWTH_DATABASE_URL": "",
        })

        with first_app.app_context():
            first_state = get_runtime_state()
            set_cache("app-isolation", {"value": "first"}, 60)

        with second_app.app_context():
            second_state = get_runtime_state()
            self.assertIsNone(get_cache("app-isolation"))

        self.assertIsNot(first_state, second_state)
        self.assertIsNot(first_state.cache, second_state.cache)
        self.assertIsNot(first_state.ai_response_cache, second_state.ai_response_cache)
        self.assertIsNot(first_state.growth_history_service, second_state.growth_history_service)
        self.assertIsNot(first_state.growth_history_repository, second_state.growth_history_repository)
        self.assertEqual(first_state.nexon_api_key, "first-app-key")
        self.assertEqual(second_state.nexon_api_key, "second-app-key")

    def test_factory_applies_configuration_and_registers_routes(self):
        app = create_app({
            "TESTING": True,
            "FLASK_SECRET_KEY": "factory-test-secret",
            "FLASK_COOKIE_SECURE": True,
            "GROWTH_DATABASE_URL": "",
        })

        self.assertTrue(app.config["TESTING"])
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.secret_key, "factory-test-secret")

        routes = {
            (rule.rule, rule.endpoint)
            for rule in app.url_map.iter_rules()
        }
        self.assertIn(("/", "pages.home"), routes)
        self.assertIn(("/admin/login", "admin.admin_login"), routes)
        self.assertIn(("/admin/logs", "admin.admin_logs"), routes)
        self.assertIn(("/api/character", "character.get_character"), routes)
        self.assertIn(("/api/history", "history.get_history"), routes)
        self.assertIn(("/api/ai-analysis", "ai.ai_analysis"), routes)
        self.assertIn(("/api/ai-comparison", "ai.ai_comparison"), routes)

        response = app.test_client().get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MAPLE GROWTH TRACKER", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
