import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.planning import PlanningEngine


class PlanningEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PlanningEngine()
        self.available_start = datetime(2026, 8, 20, 9, 0)
        self.available_end = datetime(2026, 8, 20, 11, 0)

    def make_task(self, task_id, title, duration, deadline, priority="medium", completed=False):
        return Task(
            id=task_id,
            title=title,
            duration_minutes=duration,
            deadline=deadline,
            priority=priority,
            completed=completed,
        )

    def test_normal_scheduling_assigns_consecutive_times(self):
        tasks = [
            self.make_task(1, "First", 30, self.available_start + timedelta(hours=1)),
            self.make_task(2, "Second", 45, self.available_start + timedelta(hours=2)),
        ]

        result = self.engine.generate_schedule(tasks, self.available_start, self.available_end)

        self.assertEqual([item.task_id for item in result.schedule], [1, 2])
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)
        self.assertEqual(result.schedule[0].scheduled_start, self.available_start)
        self.assertEqual(result.schedule[0].scheduled_end, self.available_start + timedelta(minutes=30))
        self.assertEqual(result.schedule[1].scheduled_start, result.schedule[0].scheduled_end)

    def test_deadline_ordering_places_overdue_then_closest_deadline(self):
        tasks = [
            self.make_task(1, "Later", 10, self.available_start + timedelta(days=2), "high"),
            self.make_task(2, "Overdue", 10, self.available_start - timedelta(minutes=1), "low"),
            self.make_task(3, "Soon", 10, self.available_start + timedelta(hours=1), "medium"),
        ]

        result = self.engine.generate_schedule(tasks, self.available_start, self.available_end)

        self.assertEqual([item.task_id for item in result.schedule], [2, 3, 1])

    def test_large_task_that_does_not_fit_allows_later_shorter_task(self):
        large_task = self.make_task(1, "Too long", 121, self.available_start + timedelta(hours=1))
        short_task = self.make_task(2, "Short task", 30, self.available_start + timedelta(hours=2))

        result = self.engine.generate_schedule([large_task, short_task], self.available_start, self.available_end)

        self.assertEqual([item.task_id for item in result.schedule], [2])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)

    def test_completed_tasks_are_ignored(self):
        completed_task = self.make_task(1, "Done", 121, self.available_start, completed=True)
        pending_task = self.make_task(2, "Pending", 30, self.available_start + timedelta(hours=1))

        result = self.engine.generate_schedule(
            [completed_task, pending_task], self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [2])
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)


if __name__ == "__main__":
    unittest.main()
