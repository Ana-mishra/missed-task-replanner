import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.recommendation import RecommendationEngine


class RecommendationEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = RecommendationEngine()
        self.now = datetime(2026, 8, 20, 9, 0)

    def make_task(
        self,
        task_id,
        title,
        duration,
        deadline,
        priority="medium",
        completed=False,
        status="pending",
        scheduled_start=None,
        scheduled_end=None,
    ):
        return Task(
            id=task_id,
            title=title,
            duration_minutes=duration,
            deadline=deadline,
            priority=priority,
            completed=completed,
            status=status,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )

    def test_overdue_task_beats_a_future_task(self):
        overdue = self.make_task(1, "Overdue", 30, self.now - timedelta(minutes=1))
        future = self.make_task(2, "Future", 30, self.now + timedelta(days=2), "high")

        result = self.engine.recommend([future, overdue], self.now)

        self.assertEqual(result.task.id, 1)
        self.assertEqual(result.reason, "Task is overdue.")

    def test_due_soon_task_beats_later_deadline_task(self):
        due_soon = self.make_task(1, "Due soon", 30, self.now + timedelta(hours=2))
        later = self.make_task(2, "Later", 30, self.now + timedelta(days=2), "high")

        result = self.engine.recommend([later, due_soon], self.now)

        self.assertEqual(result.task.id, 1)

    def test_high_priority_wins_when_deadlines_match(self):
        low = self.make_task(1, "Low", 30, self.now + timedelta(hours=2), "low")
        high = self.make_task(2, "High", 30, self.now + timedelta(hours=2), "high")

        result = self.engine.recommend([low, high], self.now)

        self.assertEqual(result.task.id, 2)

    def test_shorter_task_wins_when_other_rules_tie(self):
        longer = self.make_task(1, "Longer", 60, self.now + timedelta(hours=2), "medium")
        shorter = self.make_task(2, "Shorter", 15, self.now + timedelta(hours=2), "medium")

        result = self.engine.recommend([longer, shorter], self.now)

        self.assertEqual(result.task.id, 2)

    def test_currently_scheduled_task_is_preferred(self):
        overdue = self.make_task(1, "Overdue", 30, self.now - timedelta(minutes=1))
        active = self.make_task(
            2,
            "Active",
            30,
            self.now + timedelta(days=2),
            scheduled_start=self.now - timedelta(minutes=10),
            scheduled_end=self.now + timedelta(minutes=20),
        )

        result = self.engine.recommend([overdue, active], self.now)

        self.assertEqual(result.task.id, 2)
        self.assertEqual(result.reason, "Task is currently scheduled.")

    def test_completed_tasks_are_ignored(self):
        completed = self.make_task(1, "Completed", 30, self.now - timedelta(minutes=1), completed=True)
        available = self.make_task(2, "Available", 30, self.now + timedelta(hours=2))

        result = self.engine.recommend([completed, available], self.now)

        self.assertEqual(result.task.id, 2)

    def test_no_eligible_task_returns_clear_result(self):
        completed = self.make_task(1, "Completed", 30, self.now, completed=True)
        missed = self.make_task(
            2,
            "Old missed",
            30,
            self.now,
            status="missed",
            scheduled_end=self.now - timedelta(minutes=1),
        )

        result = self.engine.recommend([completed, missed], self.now)

        self.assertIsNone(result.task)
        self.assertEqual(result.reason, "No eligible task is available.")
