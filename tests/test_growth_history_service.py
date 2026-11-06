"""Growth history application service tests."""
import unittest
from unittest.mock import Mock

from tracker.services.growth_history_service import GrowthHistoryService


class GrowthHistoryServiceTests(unittest.TestCase):
    def test_delegates_record_reads_to_repository(self):
        repository = Mock()
        repository.get_records.return_value = [{"date": "2026-11-06"}]
        service = GrowthHistoryService(repository)

        result = service.get_records("ocid-1", "2026-11-01", "2026-11-06")

        self.assertEqual(result, [{"date": "2026-11-06"}])
        repository.get_records.assert_called_once_with(
            "ocid-1", "2026-11-01", "2026-11-06"
        )

    def test_delegates_record_writes_to_repository(self):
        repository = Mock()
        repository.save_records.return_value = 2
        service = GrowthHistoryService(repository)

        result = service.save_records("ocid-1", "밍득", "크로아", [{"date": "2026-11-06"}])

        self.assertEqual(result, 2)
        repository.save_records.assert_called_once()

    def test_exposes_repository_storage_capabilities(self):
        repository = Mock()
        repository.backend = "postgres"
        repository.uses_postgres = True
        service = GrowthHistoryService(repository)

        self.assertEqual(service.backend, "postgres")
        self.assertTrue(service.uses_postgres)


if __name__ == "__main__":
    unittest.main()
