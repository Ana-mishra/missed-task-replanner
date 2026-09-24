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
            self.event(2, 1, "scheduled", datetime(2026, 8, 10, 9, 30)),
            self.event(3, 2, "scheduled", datetime(2026, 8, 10, 9, 30)),
            self.event(4, 3, "scheduled", datetime(2026, 8, 10, 9, 30)),
            self.event(5, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(6, 2, "completed", datetime(2026, 8, 11, 11)),
            self.event(7, 1, "missed", datetime(2026, 8, 12, 10)),
            self.event(8, 1, "replanned", datetime(2026, 8, 12, 11)),
            self.event(9, 1, "recovered", datetime(2026, 8, 12, 12)),
        ]

        result = self.service.calculate(
            [completed_with_actual, completed_without_actual], history, self.week_start, self.current_time
        )

        self.assertEqual(result.tasks_created, 1)
        self.assertEqual(result.tasks_completed, 2)
        self.assertEqual(result.tasks_missed, 1)
        self.assertEqual(result.tasks_replanned, 1)
        self.assertEqual(result.tasks_recovered, 1)
        self.assertEqual(result.tasks_scheduled, 3)
        self.assertEqual(result.tasks_scheduled_completed, 2)
        self.assertAlmostEqual(result.completion_rate, 2 / 3)
        self.assertEqual(result.estimated_completed_minutes, 90)
        self.assertEqual(result.actual_completed_minutes, 45)
        self.assertEqual(result.average_estimation_difference_minutes, 15.0)
        self.assertEqual(result.postponement_cycles, 1)
        self.assertEqual(result.most_productive_day, date(2026, 8, 11))
        self.assertEqual(result.daily_completed_tasks[date(2026, 8, 11)], 2)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 2)

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
        year_result = self.service.calculate([], [], date(2026, 1, 1), self.current_time, "year")
        all_time_result = self.service.calculate([], [], date(2026, 8, 1), self.current_time, "all")

        self.assertEqual(len(month_result.daily_completed_tasks), 31)
        self.assertEqual(len(year_result.daily_completed_tasks), 12)
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

    def test_plan_stability_uses_only_scheduled_tasks_and_one_outcome_each(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 5, 10)),
            self.event(2, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(3, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(4, 2, "completed", datetime(2026, 8, 11, 10)),
            self.event(5, 3, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(6, 3, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(7, 3, "completed", datetime(2026, 8, 12, 11)),
            self.event(8, 4, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(9, 4, "missed", datetime(2026, 8, 13, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 1, "adjusted": 1, "missed": 1},
        )

    def test_plan_stability_ignores_events_before_selected_period_schedule(self):
        history = [
            self.event(1, 1, "missed", datetime(2026, 8, 5, 10)),
            self.event(2, 1, "recovered", datetime(2026, 8, 6, 10)),
            self.event(3, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(4, 1, "completed", datetime(2026, 8, 11, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 1, "adjusted": 0, "missed": 0},
        )

    def test_plan_stability_uses_later_history_to_classify_recovery(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 12, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 17, 10)),
            self.event(4, 1, "completed", datetime(2026, 8, 17, 11)),
            self.event(5, 2, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(6, 2, "missed", datetime(2026, 8, 13, 10)),
        ]

        result = self.service.calculate(
            [], history, self.week_start, datetime(2026, 8, 17, 23, 59)
        )

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 0, "adjusted": 0, "missed": 2},
        )

    def test_plan_stability_does_not_treat_overdue_as_missed(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(2, 1, "overdue", datetime(2026, 8, 12, 10)),
            self.event(3, 1, "completed", datetime(2026, 8, 12, 11)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 1, "adjusted": 0, "missed": 0},
        )

    def test_plan_stability_keeps_missed_after_recovery_and_completion(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 12, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 12, 11)),
            self.event(4, 1, "completed", datetime(2026, 8, 12, 12)),
            self.event(5, 2, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(6, 2, "rescheduled", datetime(2026, 8, 13, 10)),
            self.event(7, 2, "missed", datetime(2026, 8, 13, 11)),
            self.event(8, 2, "recovered", datetime(2026, 8, 13, 12)),
            self.event(9, 2, "completed", datetime(2026, 8, 13, 13)),
            self.event(10, 3, "scheduled", datetime(2026, 8, 14, 9)),
            self.event(11, 3, "missed", datetime(2026, 8, 14, 10)),
            self.event(12, 3, "recovered", datetime(2026, 8, 14, 11)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 0, "adjusted": 0, "missed": 3},
        )

    def test_plan_stability_deduplicates_scheduled_events(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(3, 1, "completed", datetime(2026, 8, 12, 10)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(
            result.plan_stability,
            {"stayed_as_planned": 1, "adjusted": 0, "missed": 0},
        )

    def test_recovery_overview_uses_plan_stability_missed_cohort(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "rescheduled", datetime(2026, 8, 11, 11)),
            self.event(4, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(5, 2, "missed", datetime(2026, 8, 12, 10)),
            self.event(6, 2, "recovered", datetime(2026, 8, 17, 10)),
            self.event(7, 3, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(8, 3, "missed", datetime(2026, 8, 13, 10)),
            self.event(9, 3, "replanned", datetime(2026, 8, 13, 11)),
            self.event(10, 4, "completed", datetime(2026, 8, 13, 12)),
        ]

        result = self.service.calculate(
            [], history, self.week_start, datetime(2026, 8, 17, 23, 59)
        )

        self.assertEqual(result.recovery_overview_missed, 3)
        self.assertEqual(result.recovery_overview_recovered, 2)

    def test_recovery_overview_does_not_count_rescheduled_as_recovered(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "rescheduled", datetime(2026, 8, 11, 11)),
        ]

        result = self.service.calculate([], history, self.week_start, self.current_time)

        self.assertEqual(result.recovery_overview_missed, 1)
        self.assertEqual(result.recovery_overview_recovered, 0)

    def test_scheduled_task_completed_appears_in_planned_completion_metrics(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled, 1)
        self.assertEqual(result.tasks_scheduled_completed, 1)
        self.assertEqual(result.completion_rate, 1.0)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 1)

    def test_unscheduled_task_completed_does_not_appear_in_planned_completion_metrics(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_completed, 1)  # broad event count remains
        self.assertEqual(result.tasks_scheduled, 0)
        self.assertEqual(result.tasks_scheduled_completed, 0)
        self.assertEqual(result.completion_rate, 0.0)
        self.assertEqual(result.daily_completed_tasks[date(2026, 8, 11)], 1)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 0)

    def test_scheduled_task_completed_after_another_unscheduled_completion(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 9)),  # unscheduled
            self.event(2, 2, "scheduled", datetime(2026, 8, 11, 10)),
            self.event(3, 2, "completed", datetime(2026, 8, 11, 11)),  # scheduled
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_completed, 2)  # both in broad count
        self.assertEqual(result.tasks_scheduled, 1)
        self.assertEqual(result.tasks_scheduled_completed, 1)  # only scheduled task 2
        self.assertEqual(result.completion_rate, 1.0)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 1)

    def test_multiple_completed_events_for_same_scheduled_task_counted_once(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "completed", datetime(2026, 8, 11, 12)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled, 1)
        self.assertEqual(result.tasks_scheduled_completed, 1)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 1)

    def test_completion_trend_contains_only_scheduled_cohort_completions(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),  # unscheduled
            self.event(2, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(3, 2, "completed", datetime(2026, 8, 12, 10)),  # scheduled
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.daily_completed_tasks[date(2026, 8, 11)], 1)
        self.assertEqual(result.daily_completed_tasks[date(2026, 8, 12)], 1)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 11)], 0)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 12)], 1)

    def test_deadline_behavior_ignores_unscheduled_tasks(self):
        task1 = self.task(1, completed=True)  # unscheduled with deadline
        task1.deadline = datetime(2026, 8, 11, 12)
        task2 = self.task(2, completed=True)  # scheduled with deadline
        task2.deadline = datetime(2026, 8, 12, 12)

        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),  # unscheduled, before deadline
            self.event(2, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(3, 2, "completed", datetime(2026, 8, 12, 10)),  # scheduled, before deadline
        ]
        result = self.service.calculate([task1, task2], history, self.week_start, self.current_time)
        self.assertEqual(result.deadline_behavior["completed_before_deadline"], 1)
        self.assertEqual(result.deadline_behavior["rescheduled"], 0)
        self.assertEqual(result.deadline_behavior["missed_deadline"], 0)

    def test_plan_stability_remains_unchanged(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(3, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(4, 2, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(5, 3, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(6, 3, "missed", datetime(2026, 8, 13, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 1, "adjusted": 1, "missed": 1})

    def test_recovery_overview_remains_unchanged(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 11, 11)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.recovery_overview_missed, 1)
        self.assertEqual(result.recovery_overview_recovered, 1)

    def test_empty_scheduled_cohort_returns_zero_planned_metrics(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(2, 2, "missed", datetime(2026, 8, 12, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled, 0)
        self.assertEqual(result.tasks_scheduled_completed, 0)
        self.assertEqual(result.completion_rate, 0.0)
        self.assertEqual(sum(result.daily_scheduled_completed_tasks.values()), 0)
        self.assertEqual(result.deadline_behavior, {"completed_before_deadline": 0, "rescheduled": 0, "missed_deadline": 0})
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 0})
        self.assertEqual(result.recovery_overview_missed, 0)
        self.assertEqual(result.recovery_overview_recovered, 0)

    def test_cross_period_completion_after_scheduled_anchor(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 12, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled_completed, 1)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 12)], 1)

    def test_same_task_missed_twice_counted_as_one_missed_in_plan_stability(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "missed", datetime(2026, 8, 12, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 1})

    def test_unscheduled_task_completed_and_missed_do_not_affect_plan_stability(self):
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(2, 2, "missed", datetime(2026, 8, 12, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 0})

    def test_recovery_overview_scheduled_missed_recovered_completed_counts_once(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 11, 11)),
            self.event(4, 1, "completed", datetime(2026, 8, 11, 12)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.recovery_overview_missed, 1)
        self.assertEqual(result.recovery_overview_recovered, 1)

    def test_previous_period_scheduled_recovered_task_does_not_enter_current_scheduled_cohort(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 5, 9)),  # previous period
            self.event(2, 1, "missed", datetime(2026, 8, 5, 10)),
            self.event(3, 1, "recovered", datetime(2026, 8, 11, 10)),  # current period recovery
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled, 0)
        self.assertEqual(result.tasks_scheduled_completed, 0)
        self.assertEqual(result.tasks_recovered, 1)  # broad event preserved

    def test_deadline_behavior_ignores_unscheduled_missed_task(self):
        task = self.task(1)
        task.deadline = datetime(2026, 8, 11, 12)
        history = [
            self.event(1, 1, "missed", datetime(2026, 8, 11, 14)),  # missed after deadline, but unscheduled
        ]
        result = self.service.calculate([task], history, self.week_start, self.current_time)
        self.assertEqual(result.deadline_behavior, {"completed_before_deadline": 0, "rescheduled": 0, "missed_deadline": 0})

    def test_deadline_behavior_counts_one_reschedule_event(self):
        task = self.task(1)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "rescheduled", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "completed", datetime(2026, 8, 11, 11)),
        ]
        result = self.service.calculate([task], history, self.week_start, self.current_time)
        self.assertEqual(result.deadline_behavior["rescheduled"], 1)
        self.assertEqual(result.deadline_behavior["completed_before_deadline"], 0)
        self.assertEqual(result.deadline_behavior["missed_deadline"], 0)

    def test_deadline_behavior_counts_two_reschedules_for_same_task(self):
        task = self.task(1)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "rescheduled", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(4, 1, "completed", datetime(2026, 8, 12, 11)),
        ]
        result = self.service.calculate([task], history, self.week_start, self.current_time)
        self.assertEqual(result.deadline_behavior["rescheduled"], 2)
        self.assertEqual(result.deadline_behavior["completed_before_deadline"], 0)
        self.assertEqual(result.deadline_behavior["missed_deadline"], 0)

    def test_deadline_behavior_counts_three_reschedules_across_two_tasks(self):
        # Production case: French rescheduled once, College Work twice.
        # History shows 3 events, so Stats must report 3 (not 2 tasks).
        french = self.task(1)
        college_work = self.task(2)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "rescheduled", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "completed", datetime(2026, 8, 11, 11)),
            self.event(4, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(5, 2, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(6, 2, "rescheduled", datetime(2026, 8, 13, 10)),
            self.event(7, 2, "completed", datetime(2026, 8, 13, 11)),
        ]
        result = self.service.calculate(
            [french, college_work], history, self.week_start, self.current_time
        )
        self.assertEqual(result.deadline_behavior["rescheduled"], 3)
        self.assertEqual(result.deadline_behavior["completed_before_deadline"], 0)
        self.assertEqual(result.deadline_behavior["missed_deadline"], 0)

    def test_deadline_rescheduled_matches_history_event_definition(self):
        # History counts meaningful reschedule events in range. Stats must
        # agree on the same fixture: no-op planner rows are excluded on both
        # sides, every other in-period reschedule counts once.
        task = self.task(1)
        noop = self.event(2, 1, "rescheduled", datetime(2026, 8, 11, 10))
        noop.old_start = datetime(2026, 8, 11, 9)
        noop.old_end = datetime(2026, 8, 11, 10)
        noop.new_start = datetime(2026, 8, 11, 9)
        noop.new_end = datetime(2026, 8, 11, 10)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            noop,
            self.event(3, 1, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(4, 1, "completed", datetime(2026, 8, 12, 11)),
        ]
        history_count = sum(
            1 for record in history if record.event_type == "rescheduled"
            and not (
                record.old_start is not None
                and record.old_end is not None
                and record.old_start
                == (record.new_start if record.new_start is not None else record.scheduled_start)
                and record.old_end
                == (record.new_end if record.new_end is not None else record.scheduled_end)
            )
        )
        result = self.service.calculate([task], history, self.week_start, self.current_time)
        self.assertEqual(history_count, 1)
        self.assertEqual(result.deadline_behavior["rescheduled"], history_count)

    def test_deadline_reschedule_change_leaves_other_metrics_unchanged(self):
        on_time = self.task(1)  # completed before deadline, never rescheduled
        late = self.task(2)
        late.deadline = datetime(2026, 8, 12, 12)
        rescheduled_then_late = self.task(3)
        rescheduled_then_late.deadline = datetime(2026, 8, 12, 12)
        missed_then_recovered = self.task(4)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(3, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(4, 2, "missed", datetime(2026, 8, 12, 14)),
            self.event(5, 3, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(6, 3, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(7, 3, "missed", datetime(2026, 8, 12, 14)),
            self.event(8, 4, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(9, 4, "missed", datetime(2026, 8, 13, 10)),
            self.event(10, 4, "recovered", datetime(2026, 8, 13, 11)),
        ]
        result = self.service.calculate(
            [on_time, late, rescheduled_then_late, missed_then_recovered],
            history,
            self.week_start,
            self.current_time,
        )
        # A task that ultimately misses its deadline stays missed: its
        # earlier reschedule must not leak into the rescheduled count.
        self.assertEqual(
            result.deadline_behavior,
            {"completed_before_deadline": 1, "rescheduled": 0, "missed_deadline": 2},
        )
        self.assertEqual(result.recovery_overview_missed, 3)
        self.assertEqual(result.recovery_overview_recovered, 1)
        self.assertEqual(result.tasks_recovered, 1)

    def test_deadline_behavior_ignores_out_of_period_and_post_deadline_reschedules(self):
        task = self.task(1)
        task.deadline = datetime(2026, 8, 12, 12)
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            # Before the selected week: outside the event scope entirely.
            self.event(2, 1, "rescheduled", datetime(2026, 8, 5, 10)),
            # After the deadline: not a valid reschedule.
            self.event(3, 1, "rescheduled", datetime(2026, 8, 12, 14)),
            self.event(4, 1, "completed", datetime(2026, 8, 11, 10)),
        ]
        result = self.service.calculate([task], history, self.week_start, self.current_time)
        self.assertEqual(result.deadline_behavior["rescheduled"], 0)
        self.assertEqual(result.deadline_behavior["completed_before_deadline"], 1)

    def test_previous_period_scheduled_task_completed_current_period_does_not_increase_current_cohort(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 5, 9)),  # previous period schedule
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),  # completed in current period
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.tasks_scheduled, 0)
        self.assertEqual(result.tasks_scheduled_completed, 0)
        self.assertEqual(result.tasks_completed, 1)  # broad activity preserved

    def test_all_time_period_includes_older_history_across_months(self):
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 5, 10, 9)),
            self.event(2, 1, "completed", datetime(2026, 5, 10, 10)),
            self.event(3, 2, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(4, 2, "completed", datetime(2026, 8, 11, 10)),
        ]
        result = self.service.calculate([], history, date(2026, 8, 1), self.current_time, period="all")
        self.assertEqual(result.tasks_scheduled, 2)
        self.assertEqual(result.tasks_scheduled_completed, 2)
        self.assertIn(date(2026, 5, 1), result.daily_scheduled_completed_tasks)
        self.assertIn(date(2026, 8, 1), result.daily_scheduled_completed_tasks)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 5, 1)], 1)
        self.assertEqual(result.daily_scheduled_completed_tasks[date(2026, 8, 1)], 1)


class PlanStabilityTaskListTests(unittest.TestCase):
    """Display companions to the plan_stability counts share one pass."""

    def setUp(self):
        self.service = ReflectionService()
        self.week_start = date(2026, 8, 10)
        self.current_time = datetime(2026, 8, 16, 23, 59)

    def task(self, task_id, title=None):
        task = Task(
            id=task_id,
            title=title or f"Task {task_id}",
            duration_minutes=30,
            deadline=datetime(2026, 8, 20, 10, 0),
            priority="medium",
        )
        return task

    def event(self, event_id, task_id, event_type, event_time):
        return TaskHistory(
            id=event_id,
            task_id=task_id,
            event_type=event_type,
            timestamp=event_time,
        )

    def test_task_lists_match_counts_with_real_titles(self):
        tasks = [
            self.task(1, "Book dentist appointment"),
            self.task(2, "Compare standing desk options"),
            self.task(3, "Learning French"),
        ]
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
            self.event(3, 2, "scheduled", datetime(2026, 8, 12, 9)),
            self.event(4, 2, "rescheduled", datetime(2026, 8, 12, 10)),
            self.event(5, 3, "scheduled", datetime(2026, 8, 13, 9)),
            self.event(6, 3, "missed", datetime(2026, 8, 13, 10)),
        ]
        result = self.service.calculate(tasks, history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 1, "adjusted": 1, "missed": 1})
        self.assertEqual(
            [(item.id, item.title) for item in result.plan_stability_tasks["stayed_as_planned"]],
            [(1, "Book dentist appointment")],
        )
        self.assertEqual(
            [(item.id, item.title) for item in result.plan_stability_tasks["adjusted"]],
            [(2, "Compare standing desk options")],
        )
        self.assertEqual(
            [(item.id, item.title) for item in result.plan_stability_tasks["missed"]],
            [(3, "Learning French")],
        )

    def test_missed_after_recovery_lists_task_as_missed_once(self):
        tasks = [self.task(1, "Learning French")]
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "missed", datetime(2026, 8, 11, 10)),
            self.event(3, 1, "missed", datetime(2026, 8, 12, 10)),
            self.event(4, 1, "recovered", datetime(2026, 8, 12, 11)),
            self.event(5, 1, "completed", datetime(2026, 8, 12, 12)),
        ]
        result = self.service.calculate(tasks, history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability["missed"], 1)
        self.assertEqual(len(result.plan_stability_tasks["missed"]), 1)
        self.assertEqual(result.plan_stability_tasks["missed"][0].title, "Learning French")
        self.assertEqual(result.plan_stability_tasks["stayed_as_planned"], [])
        self.assertEqual(result.plan_stability_tasks["adjusted"], [])

    def test_unscheduled_and_comparison_period_tasks_are_excluded(self):
        tasks = [self.task(1, "Current task")]
        history = [
            self.event(1, 1, "completed", datetime(2026, 8, 11, 10)),  # unscheduled
            self.event(2, 2, "missed", datetime(2026, 8, 12, 10)),  # unscheduled
            self.event(3, 3, "scheduled", datetime(2026, 8, 5, 9)),  # previous period
            self.event(4, 3, "missed", datetime(2026, 8, 5, 10)),
        ]
        result = self.service.calculate(tasks, history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 0})
        self.assertEqual(
            result.plan_stability_tasks,
            {"stayed_as_planned": [], "adjusted": [], "missed": []},
        )

    def test_deleted_task_keeps_title_through_history_snapshot(self):
        # The task row is gone (ON DELETE SET NULL cleared task_id), but the
        # events captured the title when written.
        history = [
            TaskHistory(
                id=1, task_id=None, event_type="scheduled",
                timestamp=datetime(2026, 8, 11, 9), task_title="Learning French",
            ),
            TaskHistory(
                id=2, task_id=None, event_type="missed",
                timestamp=datetime(2026, 8, 11, 10), task_title="Learning French",
            ),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 1})
        self.assertEqual(len(result.plan_stability_tasks["missed"]), 1)
        self.assertIsNone(result.plan_stability_tasks["missed"][0].id)
        self.assertEqual(result.plan_stability_tasks["missed"][0].title, "Learning French")

    def test_live_task_prefers_current_title_over_stale_snapshot(self):
        tasks = [self.task(1, "Renamed task")]
        history = [
            self.event(1, 1, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, 1, "completed", datetime(2026, 8, 11, 10)),
        ]
        history[0].task_title = "Old name"
        history[1].task_title = "Old name"
        result = self.service.calculate(tasks, history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability_tasks["stayed_as_planned"][0].title, "Renamed task")

    def test_genuinely_unavailable_title_is_omitted_gracefully(self):
        # Old rows predate the snapshot column: NULL task_id and NULL title.
        history = [
            self.event(1, None, "scheduled", datetime(2026, 8, 11, 9)),
            self.event(2, None, "missed", datetime(2026, 8, 11, 10)),
        ]
        result = self.service.calculate([], history, self.week_start, self.current_time)
        self.assertEqual(result.plan_stability, {"stayed_as_planned": 0, "adjusted": 0, "missed": 1})
        self.assertEqual(result.plan_stability_tasks["missed"], [])
