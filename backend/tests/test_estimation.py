import unittest
from datetime import datetime

from app.models.task import Task
from app.services.estimation import EstimationService


class EstimationServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = EstimationService()

    def make_task(self, task_id, estimate, actual=None, completed=True):
        return Task(
            id=task_id,
            title=f"Task {task_id}",
            duration_minutes=estimate,
            actual_duration_minutes=actual,
            deadline=datetime(2040, 1, 1, 10, 0),
            priority="medium",
            completed=completed,
        )

    def test_no_eligible_completed_tasks_returns_insufficient_data(self):
        result = self.service.calculate([self.make_task(1, 30, completed=False)])

        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.tendency, "insufficient_data")

    def test_accurately_estimated_task(self):
        result = self.service.calculate([self.make_task(1, 30, 30)])

        self.assertEqual(result.total_difference_minutes, 0)
        self.assertEqual(result.average_accuracy_percent, 100.0)
        self.assertEqual(result.tendency, "accurate")

    def test_underestimated_task(self):
        result = self.service.calculate([self.make_task(1, 30, 45)])

        self.assertEqual(result.total_difference_minutes, 15)
        self.assertEqual(result.tendency, "underestimate")

    def test_overestimated_task(self):
        result = self.service.calculate([self.make_task(1, 60, 30)])

        self.assertEqual(result.total_difference_minutes, -30)
        self.assertEqual(result.tendency, "overestimate")

    def test_multiple_completed_tasks_are_aggregated(self):
        result = self.service.calculate(
            [self.make_task(1, 30, 45), self.make_task(2, 60, 30)]
        )

        self.assertEqual(result.completed_tasks, 2)
        self.assertEqual(result.estimated_minutes, 90)
        self.assertEqual(result.actual_minutes, 75)
        self.assertEqual(result.total_difference_minutes, -15)
        self.assertEqual(result.average_difference_minutes, -7.5)
        self.assertEqual(result.average_accuracy_percent, 50.0)

    def test_tasks_without_actual_duration_are_ignored(self):
        result = self.service.calculate([self.make_task(1, 30, 30), self.make_task(2, 60)])

        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(result.estimated_minutes, 30)

    def test_incomplete_tasks_are_ignored(self):
        result = self.service.calculate([self.make_task(1, 30, 45, completed=False)])

        self.assertEqual(result.completed_tasks, 0)
