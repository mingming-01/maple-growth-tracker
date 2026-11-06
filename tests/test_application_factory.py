"""Flask application factory and blueprint registration tests."""
import unittest

from tracker import create_app


class ApplicationFactoryTests(unittest.TestCase):
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
