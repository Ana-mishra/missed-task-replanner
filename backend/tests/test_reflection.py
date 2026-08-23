import unittest
from datetime import date, datetime, timedelta

from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services.progress import ProgressService
from app.services.reflection import ReflectionService


class ReflectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ReflectionService()
        self.week_start = date(2026, 8, 10)
        self.current_time = datetime(2026, 8, 16, 23, 59)

    def task(self, task_id, estimate=30, actual=None, completed=False):
        return Task(
            id=task_id,
            title=f"Task {task_id}",
            duration_minutes=estimate,
            actual_duration_minutes=actual,
            deadline=datetime(2026, 8, 20, 10, 0),
            priority="medium",
            completed=completed,
        )

    def event(self, event_id, task_id, event_type, event_time):
        return TaskHistory(
            id=event_id,
            task_id=task_id,
            event_type=event_type,
            timestamp=event_time,
        )

    def test_empty_week_has_sensible_zero_and_null_values(self):
        result = self.service.calculate([], [], self.week_start, self.current_time)

        self.assertEqual(result.week_end, date(2026, 8, 16))
        self.assertEqual(result.tasks_completed, 0)
        self.assertEqual(result.completion_rate, 0.0)
        self.assertIsNone(result.average_estimation_difference_minutes)
        self.assertIsNone(result.most_productive_day)
        self.assertEqual(len(result.daily_completed_tasks), 7)

    def test_weekly_activity_estimation_and_postponement_statistics(self):
        completed_with_actual = self.task(1, estimate=30, actual=45, completed=True)
        completed_without_actual = self.task(2, estimate=60, completed=True)
        history = [
            self.event(1, 1, "created", datetime(2026, 8, 10, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(3, 2, "completed", datetime(2026, 8, 11, 11)),
            self.event(4, 1, "missed", datetime(2026, 8, 12, 10)),
            self.event(5, 1, "replanned", datetime(2026, 8, 12, 11)),
            self.event(6, 1, "recovered", datetime(2026, 8, 12, 12)),
        ]

        result = self.service.calculate(
            [completed_with_actual, completed_without_actual], history, self.week_start, self.current_time
        )

        self.assertEqual(result.tasks_created, 1)
        self.assertEqual(result.tasks_completed, 2)
        self.assertEqual(result.tasks_missed, 1)
        self.assertEqual(result.tasks_replanned, 1)
        self.assertEqual(result.tasks_recovered, 1)
        self.assertAlmostEqual(result.completion_rate, 2 / 3)
        self.assertEqual(result.estimated_completed_minutes, 90)
        self.assertEqual(result.actual_completed_minutes, 45)
        self.assertEqual(result.average_estimation_difference_minutes, 15.0)
        self.assertEqual(result.postponement_cycles, 1)
        self.assertEqual(result.most_productive_day, date(2026, 8, 11))
        self.assertEqual(result.daily_completed_tasks[date(2026, 8, 11)], 2)

    def test_daily_planned_minutes_use_scheduled_interval(self):
        scheduled_task = self.task(1, estimate=120, actual=90, completed=True)
        scheduled_task.scheduled_start = datetime(2026, 8, 11, 9)
        scheduled_task.scheduled_end = datetime(2026, 8, 11, 9, 45)
        history = [self.event(1, 1, "completed", datetime(2026, 8, 11, 10))]

        result = self.service.calculate(
            [scheduled_task], history, self.week_start, self.current_time
        )

        self.assertEqual(result.daily_planned_minutes[date(2026, 8, 11)], 45)
        self.assertEqual(result.daily_actual_minutes[date(2026, 8, 11)], 90)

    def test_previous_week_summary_values_are_separate_from_current_week(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 5, 10)),
            self.event(2, 1, "missed", datetime(2026, 8, 6, 10)),
            self.event(3, 1, "completed", datetime(2026, 8, 11, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.tasks_completed, 1)
        self.assertEqual(result.previous_tasks_completed, 1)
        self.assertEqual(result.previous_tasks_missed, 1)
        self.assertEqual(result.previous_tasks_recovered, 0)
        self.assertEqual(result.previous_completion_rate, 0.5)

    def test_all_time_summary_has_no_invented_previous_period(self):
        result = self.service.calculate([], [], self.week_start, self.current_time, "all")

        self.assertIsNone(result.previous_tasks_completed)
        self.assertIsNone(result.previous_completion_rate)

    def test_month_and_all_time_use_period_buckets(self):
        month_result = self.service.calculate([], [], date(2026, 8, 1), self.current_time, "month")
        all_time_result = self.service.calculate([], [], date(2026, 8, 1), self.current_time, "all")

        self.assertEqual(len(month_result.daily_completed_tasks), 31)
        self.assertEqual(list(all_time_result.daily_completed_tasks), [date(2026, 8, 1)])

    def test_recovery_rate_comparison_supports_positive_change(self):
        history = [
            self.event(1, 1, "missed", datetime(2026, 8, 5, 10)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 11, 11)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.tasks_recovered, 1)
        self.assertEqual(result.previous_tasks_recovered, 0)
        self.assertEqual(result.previous_tasks_missed, 1)

    def test_recovery_rate_comparison_supports_negative_change(self):
        history = [
            self.event(1, 1, "missed", datetime(2026, 8, 5, 10)),
            self.event(2, 1, "recovered", datetime(2026, 8, 5, 11)),
            self.event(3, 1, "missed", datetime(2026, 8, 11, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.tasks_recovered, 0)
        self.assertEqual(result.previous_tasks_recovered, 1)
        self.assertEqual(result.previous_tasks_missed, 1)

    def test_most_productive_day_tie_uses_earliest_date(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(2, 2, "completed", datetime(2026, 8, 12, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.most_productive_day, date(2026, 8, 11))

    def test_events_outside_week_and_future_events_are_excluded(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 9, 23, 59)),
            self.event(2, 1, "completed", datetime(2026, 8, 17, 0, 0)),
            self.event(3, 1, "completed", datetime(2026, 8, 16, 23, 59, 30)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.tasks_completed, 0)

    def test_progress_level_and_percent_reuse_progress_service(self):
        tasks = [self.task(task_id, completed=True) for task_id in range(5)]
        expected = ProgressService().calculate(tasks, [], self.current_time.date())

        result = self.service.calculate(tasks, [], self.week_start, self.current_time)

        self.assertEqual(result.progress_level, expected.progress_level)
        self.assertEqual(result.progress_percent, expected.progress_percent)
