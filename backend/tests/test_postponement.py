import unittest
from datetime import datetime, timedelta

from app.models.task_history import TaskHistory
from app.services.postponement import PostponementService


class PostponementServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = PostponementService()
        self.start = datetime(2040, 1, 1, 9, 0)

    def record(self, record_id, event_type, minutes):
        return TaskHistory(
            id=record_id,
            task_id=1,
            event_type=event_type,
            timestamp=self.start + timedelta(minutes=minutes),
        )

    def test_task_with_no_postponements(self):
        result = self.service.analyze(1, [self.record(1, "created", 0)])

        self.assertEqual(result.postponement_count, 0)
        self.assertIsNone(result.last_postponed_at)
        self.assertFalse(result.needs_review)

    def test_one_missed_and_replanned_cycle(self):
        result = self.service.analyze(
            1,
            [self.record(1, "missed", 0), self.record(2, "replanned", 10)],
        )

        self.assertEqual(result.postponement_count, 1)
        self.assertEqual(result.last_postponed_at, self.start + timedelta(minutes=10))

    def test_multiple_cycles_reach_default_review_threshold(self):
        records = [
            self.record(1, "missed", 0),
            self.record(2, "replanned", 1),
            self.record(3, "missed", 2),
            self.record(4, "replanned", 3),
            self.record(5, "missed", 4),
            self.record(6, "replanned", 5),
        ]

        result = self.service.analyze(1, records)

        self.assertEqual(result.postponement_count, 3)
        self.assertTrue(result.needs_review)

    def test_custom_threshold_is_used(self):
        records = [self.record(1, "missed", 0), self.record(2, "replanned", 1)]

        result = self.service.analyze(1, records, review_threshold=1)

        self.assertTrue(result.needs_review)

    def test_unrelated_events_do_not_count_as_postponements(self):
        records = [
            self.record(1, "created", 0),
            self.record(2, "scheduled", 1),
            self.record(3, "completed", 2),
            self.record(4, "deleted", 3),
        ]

        result = self.service.analyze(1, records)

        self.assertEqual(result.postponement_count, 0)
