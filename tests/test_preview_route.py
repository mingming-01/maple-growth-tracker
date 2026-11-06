"""Tests for React root rollout and the retained legacy route."""
import tempfile
import unittest
from pathlib import Path

from tracker import create_app


class ReactPreviewRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "FLASK_SECRET_KEY": "react-preview-test-secret",
        })
        self.client = self.app.test_client()

    def test_react_root_and_legacy_routes_are_registered(self):
        routes = {
            (rule.rule, rule.endpoint)
            for rule in self.app.url_map.iter_rules()
        }
        self.assertIn(("/", "pages.home"), routes)
        self.assertIn(("/legacy/", "pages.legacy_home"), routes)
        self.assertIn(("/preview/", "pages.react_preview"), routes)
        self.assertIn(("/preview/<path:asset_path>", "pages.react_preview_asset"), routes)

        legacy = self.client.get("/legacy/")
        self.assertEqual(legacy.status_code, 200)
        self.assertIn("MAPLE GROWTH TRACKER", legacy.get_data(as_text=True))

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        built_index = Path(self.app.static_folder) / "react-preview" / "index.html"
        if built_index.is_file():
            self.assertIn("/static/react-preview/assets/", home.get_data(as_text=True))
        else:
            self.assertIn("MAPLE GROWTH TRACKER", home.get_data(as_text=True))

    def test_home_falls_back_to_legacy_when_react_build_is_missing(self):
        with tempfile.TemporaryDirectory() as empty_static:
            self.app.static_folder = empty_static
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MAPLE GROWTH TRACKER", response.get_data(as_text=True))

    def test_preview_route_is_explicit_when_build_is_missing(self):
        with tempfile.TemporaryDirectory() as empty_static:
            self.app.static_folder = empty_static
            response = self.client.get("/preview/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("React 미리보기 빌드가 필요합니다", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
