"""Tests for the separately mounted React preview page."""
import unittest

from tracker import create_app


class ReactPreviewRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "FLASK_SECRET_KEY": "react-preview-test-secret",
        })
        self.client = self.app.test_client()

    def test_preview_route_is_registered_without_replacing_home(self):
        routes = {
            (rule.rule, rule.endpoint)
            for rule in self.app.url_map.iter_rules()
        }
        self.assertIn(("/preview/", "pages.react_preview"), routes)
        self.assertIn(("/preview/<path:asset_path>", "pages.react_preview_asset"), routes)
        self.assertIn(("/", "pages.home"), routes)

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("MAPLE GROWTH TRACKER", home.get_data(as_text=True))

    def test_preview_route_is_explicit_when_build_is_missing(self):
        response = self.client.get("/preview/")
        self.assertIn(response.status_code, (200, 503))
        if response.status_code == 503:
            self.assertIn("React 미리보기 빌드가 필요합니다", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()