"""Capacity-overload planning outcomes.

The planner detects overload itself (`is_overloaded` / `unscheduled_minutes`
from PlanningEngine.generate_schedule) and the Plan page explains those exact
numbers. These tests lock the planner behavior the explanation relies on:
every skipped minute is a capacity skip, including the zero-scheduled case.
"""
import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.planning import PlanningEngine


class CapacityOverloadTests(unittest.TestCase):
    def setUp(self):
        self.engine = PlanningEngine()
        self.available_start = datetime(2026, 8, 20, 9, 0)

    def make_task(
        self,
        task_id,
        title,
        duration,
        priority="medium",
        completed=False,
        energy_level="medium",
    ):
        return Task(
            id=task_id,
            title=title,
            duration_minutes=duration,
            # Far-future deadline: no deadline protection involved, so any
            # unscheduled outcome here is capacity only.
            deadline=self.available_start + timedelta(days=7),
            priority=priority,
            completed=completed,
            energy_level=energy_level,
        )

    def plan(self, tasks, available_minutes, **kwargs):
        return self.engine.generate_schedule(
            tasks,
            self.available_start,
            self.available_start + timedelta(minutes=available_minutes),
            **kwargs,
        )

    def test_single_task_slightly_over_capacity(self):
        result = self.plan([self.make_task(1, "French", 45)], 39)
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 45)
        self.assertEqual(result.schedule, [])

    def test_two_tasks_over_capacity_leaves_both_unscheduled(self):
        result = self.plan(
            [
                self.make_task(1, "French", 45),
                self.make_task(2, "Essay writing", 45),
            ],
            39,
        )
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 90)
        self.assertEqual(result.schedule, [])

    def test_enough_capacity_schedules_everything(self):
        result = self.plan(
            [
                self.make_task(1, "French", 45),
                self.make_task(2, "Essay writing", 45),
            ],
            120,
        )
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)
        self.assertEqual(len(result.schedule), 2)

    def test_partial_fit_schedules_one_task_and_reports_the_other(self):
        result = self.plan(
            [
                self.make_task(1, "French", 45),
                self.make_task(2, "Essay writing", 45),
            ],
            60,
        )
        self.assertTrue(result.is_overloaded)
        self.assertEqual(len(result.schedule), 1)
        self.assertEqual(result.unscheduled_minutes, 45)

    def test_bad_day_behavior_unchanged(self):
        result = self.plan(
            [
                self.make_task(1, "French", 45, energy_level="low"),
                self.make_task(2, "Essay writing", 45, energy_level="low"),
            ],
            60,
            bad_day=True,
        )
        self.assertTrue(result.bad_day)
        self.assertTrue(result.is_overloaded)
        # Reduced 60% target (36 min) fits neither 45-minute task.
        self.assertEqual(result.unscheduled_minutes, 90)

    def test_no_tasks_is_not_overloaded(self):
        result = self.plan([], 39)
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)

    def test_zero_duration_and_completed_tasks_are_not_capacity(self):
        result = self.plan(
            [
                self.make_task(1, "Zero", 0),
                self.make_task(2, "Done", 30, completed=True),
                self.make_task(3, "Fits", 30),
            ],
            60,
        )
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)
        self.assertEqual([item.task_id for item in result.schedule], [3])


if __name__ == "__main__":
    unittest.main()
