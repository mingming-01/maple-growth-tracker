"""Deployment entrypoint and Gunicorn timeout regression tests."""
import re
import runpy
from pathlib import Path
import subprocess
import sys
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

    def test_render_start_command_loads_project_gunicorn_config_by_default(self):
        """Render configured gunicorn app:app must resolve the repository config."""
        result = subprocess.run(
            [sys.executable, "-m", "gunicorn", "--print-config", "app:app"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )

        timeout_match = re.search(r"(?m)^timeout\s*=\s*(\d+)\s*$", result.stdout)
        self.assertIsNotNone(timeout_match, msg=result.stdout[-4000:])
        self.assertEqual(timeout_match.group(1), "120")


if __name__ == "__main__":
    unittest.main()
