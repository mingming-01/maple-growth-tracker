"""React 단일 메인 진입점 라우트 테스트."""
import tempfile
import unittest
from pathlib import Path

from tracker import create_app


class ReactRootRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "GROWTH_DATABASE_URL": "",
            "FLASK_SECRET_KEY": "react-root-test-secret",
        })
        self.client = self.app.test_client()

    def test_only_root_route_serves_react_and_legacy_routes_are_retired(self):
        routes = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn("/", routes)
        for retired in ("/legacy", "/legacy/", "/preview", "/preview/", "/preview/<path:asset_path>"):
            self.assertNotIn(retired, routes)

        with tempfile.TemporaryDirectory() as static_dir:
            build_dir = Path(static_dir) / "react-preview"
            build_dir.mkdir()
            (build_dir / "index.html").write_text(
                '<div id="root">React production entry</div>',
                encoding="utf-8",
            )
            self.app.static_folder = static_dir
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("React production entry", response.get_data(as_text=True))

    def test_root_returns_service_unavailable_when_react_build_is_missing(self):
        with tempfile.TemporaryDirectory() as empty_static:
            self.app.static_folder = empty_static
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("React 프런트엔드 빌드가 없습니다", response.get_data(as_text=True))
        self.assertNotIn("templates/index.html", response.get_data(as_text=True))

    def test_retired_legacy_and_preview_paths_return_not_found(self):
        for path in ("/legacy", "/legacy/", "/preview", "/preview/", "/preview/assets/index.js"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
