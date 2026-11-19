"""Deployment entrypoint and Gunicorn timeout regression tests."""
import runpy
from pathlib import Path
import unittest

from tracker.config import Config


ROOT = Path(__file__).resolve().parents[1]


class GunicornRuntimeConfigTests(unittest.TestCase):
    def test_procfile_uses_the_shared_gunicorn_config(self):
        command = (ROOT / "Procfile").read_text(encoding="utf-8").strip()

        self.assertIn("gunicorn --config gunicorn.conf.py app:app", command)
        self.assertNotIn("--timeout", command)

    def test_worker_timeout_exceeds_the_end_to_end_ai_budget(self):
        config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))

        self.assertGreater(config["timeout"], Config.AI_REQUEST_TOTAL_TIMEOUT)
        self.assertEqual(config["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
