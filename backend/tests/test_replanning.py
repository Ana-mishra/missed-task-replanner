import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.replanning import ReplanningEngine


class ReplanningEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReplanningEngine()
        self.available_start = datetime(2026, 8, 20, 9, 0)
        self.available_end = datetime(2026, 8, 20, 12, 0)

    def make_task(self, task_id, title, duration, deadline, priority="medium", completed=False):
        return Task(
            id=task_id,
            title=title,
            duration_minutes=duration,
            deadline=deadline,
            priority=priority,
            completed=completed,
        )

    def test_missed_task_is_rescheduled_when_it_fits(self):
        missed_task = self.make_task(
            1, "Missed task", 30, self.available_start + timedelta(hours=1)
        )

        result = self.engine.generate_revised_schedule(
            [], missed_task, self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertFalse(result.is_overloaded)

    def test_urgent_tasks_remain_ahead_of_flexible_tasks(self):
        urgent_task = self.make_task(
            1, "Urgent", 30, self.available_start + timedelta(hours=1), "low"
        )
        flexible_task = self.make_task(
            2, "Flexible", 30, self.available_start + timedelta(days=3), "high"
        )
        missed_task = self.make_task(
            3, "Missed", 30, self.available_start + timedelta(days=2), "medium"
        )

        result = self.engine.generate_revised_schedule(
            [urgent_task, flexible_task], missed_task, self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [1, 3, 2])

    def test_overload_reports_unscheduled_work(self):
        urgent_task = self.make_task(
            1, "Urgent", 90, self.available_start + timedelta(hours=1)
        )
        missed_task = self.make_task(
            2, "Missed", 120, self.available_start + timedelta(days=1)
        )
        available_end = self.available_start + timedelta(hours=2)

        result = self.engine.generate_revised_schedule(
            [urgent_task], missed_task, self.available_start, available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 120)

    def test_completed_tasks_are_excluded(self):
        completed_task = self.make_task(
            1, "Completed", 30, self.available_start, completed=True
        )
        missed_task = self.make_task(
            2, "Missed", 30, self.available_start + timedelta(hours=1)
        )

        result = self.engine.generate_revised_schedule(
            [completed_task], missed_task, self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [2])

    def test_replanning_recalculates_instead_of_appending_missed_task(self):
        flexible_task = self.make_task(
            1, "Flexible", 30, self.available_start + timedelta(days=2), "high"
        )
        missed_task = self.make_task(
            2, "Missed overdue", 30, self.available_start - timedelta(minutes=1), "low"
        )

        result = self.engine.generate_revised_schedule(
            [flexible_task], missed_task, self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [2, 1])
        self.assertEqual(result.schedule[0].scheduled_start, self.available_start)


if __name__ == "__main__":
    unittest.main()
