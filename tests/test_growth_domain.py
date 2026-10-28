import unittest

from domain.growth_calculations import (
    calculate_archive_history_changes,
    calculate_recent_history_changes,
)


class RecentHistoryCalculationTests(unittest.TestCase):
    def test_calculates_experience_and_ranking_changes(self):
        history = [
            {
                "date": "2026-10-25",
                "level": 280,
                "experience": 1000,
                "ranking": 30,
            },
            {
                "date": "2026-10-26",
                "level": 280,
                "experience": 1500,
                "ranking": 25,
            },
            {
                "date": "2026-10-27",
                "level": 281,
                "experience": 100,
                "ranking": 20,
            },
        ]

        result = calculate_recent_history_changes(history)

        self.assertIsNone(result[0]["experienceChange"])
        self.assertIsNone(result[0]["rankingChange"])
        self.assertEqual(result[1]["experienceChange"], 500)
        self.assertEqual(result[1]["rankingChange"], 5)
        self.assertFalse(result[1]["levelUp"])
        self.assertIsNone(result[2]["experienceChange"])
        self.assertEqual(result[2]["rankingChange"], 5)
        self.assertTrue(result[2]["levelUp"])


class ArchiveHistoryCalculationTests(unittest.TestCase):
    def test_calculates_only_between_consecutive_available_records(self):
        history = [
            {
                "date": "2026-10-01",
                "recordStatus": "available",
                "level": 280,
                "experience": 1000,
                "ranking": 300,
            },
            {
                "date": "2026-10-02",
                "recordStatus": "available",
                "level": 280,
                "experience": 1500,
                "ranking": 290,
            },
            {
                "date": "2026-10-03",
                "recordStatus": "not_ready",
                "level": None,
                "experience": None,
                "ranking": None,
            },
            {
                "date": "2026-10-04",
                "recordStatus": "available",
                "level": 280,
                "experience": 2500,
                "ranking": 270,
            },
            {
                "date": "2026-10-05",
                "recordStatus": "available",
                "level": 281,
                "experience": 100,
                "ranking": 260,
            },
        ]

        result = calculate_archive_history_changes(history)

        self.assertEqual(result[1]["experienceChange"], 500)
        self.assertEqual(result[1]["rankingChange"], 10)
        self.assertIsNone(result[2]["experienceChange"])
        self.assertIsNone(result[3]["experienceChange"])
        self.assertIsNone(result[3]["rankingChange"])
        self.assertTrue(result[4]["levelUp"])
        self.assertIsNone(result[4]["experienceChange"])
        self.assertEqual(result[4]["rankingChange"], 10)

    def test_keeps_missing_record_status_unchanged(self):
        history = [
            {
                "date": "2026-10-01",
                "recordStatus": "not_collected",
                "level": None,
                "experience": None,
                "ranking": None,
            }
        ]

        result = calculate_archive_history_changes(history)

        self.assertEqual(result[0]["recordStatus"], "not_collected")
        self.assertIsNone(result[0]["experienceChange"])
        self.assertIsNone(result[0]["rankingChange"])
        self.assertFalse(result[0]["levelUp"])


if __name__ == "__main__":
    unittest.main()
