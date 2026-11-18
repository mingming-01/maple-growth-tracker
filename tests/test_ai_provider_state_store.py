"""Tests for shared AI provider cooldown state."""
import tempfile
import time
import unittest
from pathlib import Path

from tracker.repositories.ai_provider_state_store import AIProviderStateStore


class AIProviderStateStoreTests(unittest.TestCase):
    def test_cooldown_is_shared_between_store_instances(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "provider-state.sqlite3")
            first = AIProviderStateStore(sqlite_path=path)
            second = AIProviderStateStore(sqlite_path=path)
            until = time.time() + 600

            first.set_cooldown_until("gemini", until)

            self.assertEqual(second.get_cooldown_until("gemini"), until)

    def test_later_cooldown_cannot_be_shortened(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AIProviderStateStore(sqlite_path=str(Path(temp_dir) / "provider-state.sqlite3"))
            later = time.time() + 900
            store.set_cooldown_until("gemini", later)
            store.set_cooldown_until("gemini", time.time() + 60)

            self.assertEqual(store.get_cooldown_until("gemini"), later)

    def test_cooldown_can_be_cleared_after_provider_recovers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AIProviderStateStore(sqlite_path=str(Path(temp_dir) / "provider-state.sqlite3"))
            store.set_cooldown_until("gemini", time.time() + 300)
            store.clear_cooldown("gemini")

            self.assertEqual(store.get_cooldown_until("gemini"), 0.0)


if __name__ == "__main__":
    unittest.main()
