import unittest
from datetime import date, datetime, timedelta

from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services.progress import ProgressService


class ProgressServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ProgressService()
        self.today = date(2040, 1, 10)

    def task(self, task_id, completed=False, estimate=30, actual=None):
        return Task(
            id=task_id,
            title=f"Task {task_id}",
            duration_minutes=estimate,
            actual_duration_minutes=actual,
            deadline=datetime(2040, 1, 20, 10, 0),
            priority="medium",
            completed=completed,
        )

    def completed_event(self, record_id, event_date):
        return TaskHistory(
            id=record_id,
            task_id=1,
            event_type="completed",
            timestamp=datetime.combine(event_date, datetime.min.time()),
        )

    def test_no_tasks_returns_zero_progress(self):
        result = self.service.calculate([], [], self.today)

        self.assertEqual(result.completed_tasks, 0)
        self.assertEqual(result.completion_rate, 0.0)
        self.assertEqual(result.progress_level, 1)
        self.assertEqual(result.progress_percent, 0.0)

    def test_completed_and_incomplete_tasks_calculate_totals_and_rate(self):
        result = self.service.calculate(
            [self.task(1, True, 30, 25), self.task(2, True, 60), self.task(3, False, 20)],
            [],
            self.today,
        )

        self.assertEqual(result.completed_tasks, 2)
        self.assertEqual(result.completed_minutes, 25)
        self.assertEqual(result.estimated_completed_minutes, 90)
        self.assertAlmostEqual(result.completion_rate, 66.6666666667)

    def test_one_day_streak(self):
        result = self.service.calculate([], [self.completed_event(1, self.today)], self.today)

        self.assertEqual(result.current_streak_days, 1)

    def test_multiple_consecutive_streak_days(self):
        history = [
            self.completed_event(1, self.today),
            self.completed_event(2, self.today - timedelta(days=1)),
            self.completed_event(3, self.today - timedelta(days=2)),
        ]

        result = self.service.calculate([], history, self.today)

        self.assertEqual(result.current_streak_days, 3)

    def test_missed_day_breaks_streak(self):
        history = [
            self.completed_event(1, self.today),
            self.completed_event(2, self.today - timedelta(days=2)),
        ]

        result = self.service.calculate([], history, self.today)

        self.assertEqual(result.current_streak_days, 1)

    def test_multiple_completions_on_one_day_count_once(self):
        history = [self.completed_event(1, self.today), self.completed_event(2, self.today)]

        result = self.service.calculate([], history, self.today)

        self.assertEqual(result.current_streak_days, 1)

    def test_future_completion_events_do_not_count(self):
        history = [self.completed_event(1, self.today + timedelta(days=1))]

        result = self.service.calculate([], history, self.today)

        self.assertEqual(result.current_streak_days, 0)

    def test_progress_levels_and_percentages(self):
        cases = [(0, 1, 0.0), (4, 1, 80.0), (5, 2, 0.0), (9, 2, 80.0), (10, 3, 0.0), (20, 4, 0.0)]
        for count, level, percent in cases:
            with self.subTest(count=count):
                result = self.service.calculate(
                    [self.task(task_id, completed=True) for task_id in range(count)], [], self.today
                )
                self.assertEqual(result.progress_level, level)
                self.assertEqual(result.progress_percent, percent)

    def test_level_five_returns_full_progress(self):
        result = self.service.calculate(
            [self.task(task_id, completed=True) for task_id in range(35)], [], self.today
        )

        self.assertEqual(result.progress_level, 5)
        self.assertEqual(result.progress_percent, 100.0)

    def test_current_date_determines_streak(self):
        event_date = date(2040, 1, 5)
        history = [self.completed_event(1, event_date)]

        result = self.service.calculate([], history, event_date)

        self.assertEqual(result.current_streak_days, 1)

    def test_deleted_tasks_do_not_affect_current_completion_rate(self):
        current_task = self.task(1, completed=True)
        deleted_task_history = self.completed_event(2, self.today)

        result = self.service.calculate([current_task], [deleted_task_history], self.today)

        self.assertEqual(result.completion_rate, 100.0)
