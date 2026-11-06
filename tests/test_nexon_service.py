"""Nexon application service tests."""
import unittest
from unittest.mock import Mock, patch

from tracker.services import nexon_service


class NexonServiceTests(unittest.TestCase):
    @patch("tracker.services.nexon_service.get_basic_character")
    @patch("tracker.services.nexon_service.get_ocid")
    def test_resolves_character_identity_and_basic_data(self, get_ocid, get_basic):
        id_response = Mock()
        basic_response = Mock()
        basic = {"character_name": "밍득", "character_level": 297}
        get_ocid.return_value = ("ocid-value", id_response)
        get_basic.return_value = (basic, basic_response)

        ocid, resolved_basic, response = nexon_service.resolve_character("밍득")

        self.assertEqual(ocid, "ocid-value")
        self.assertEqual(resolved_basic, basic)
        self.assertIs(response, basic_response)
        get_ocid.assert_called_once_with("밍득")
        get_basic.assert_called_once_with("ocid-value")

    @patch("tracker.services.nexon_service.get_basic_character")
    @patch("tracker.services.nexon_service.get_ocid")
    def test_stops_when_character_id_cannot_be_resolved(self, get_ocid, get_basic):
        failed_response = Mock(status_code=404)
        get_ocid.return_value = (None, failed_response)

        ocid, basic, response = nexon_service.resolve_character("없는캐릭터")

        self.assertIsNone(ocid)
        self.assertIsNone(basic)
        self.assertIs(response, failed_response)
        get_basic.assert_not_called()

    def test_temporary_failure_classifier(self):
        self.assertTrue(nexon_service.is_temporary_nexon_failure(None))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=429)))
        self.assertTrue(nexon_service.is_temporary_nexon_failure(Mock(status_code=503)))
        self.assertFalse(nexon_service.is_temporary_nexon_failure(Mock(status_code=404)))


if __name__ == "__main__":
    unittest.main()
