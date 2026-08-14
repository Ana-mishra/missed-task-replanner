import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.planning import PlanningEngine


class PlanningEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PlanningEngine()
        self.available_start = datetime(2026, 8, 20, 9, 0)
        self.available_end = datetime(2026, 8, 20, 11, 0)

    def make_task(
        self,
        task_id,
        title,
        duration,
        deadline,
        priority="medium",
        completed=False,
        energy_level="medium",
    ):
        return Task(
            id=task_id,
            title=title,
            duration_minutes=duration,
            deadline=deadline,
            priority=priority,
            completed=completed,
            energy_level=energy_level,
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

    def test_low_user_energy_prefers_low_energy_task_when_other_rules_tie(self):
        deadline = self.available_start + timedelta(hours=2)
        high_energy = self.make_task(1, "High energy", 30, deadline, energy_level="high")
        low_energy = self.make_task(2, "Low energy", 30, deadline, energy_level="low")

        result = self.engine.generate_schedule(
            [high_energy, low_energy], self.available_start, self.available_end, "low"
        )

        self.assertEqual([item.task_id for item in result.schedule], [2, 1])

    def test_medium_user_energy_prefers_medium_energy_task_when_other_rules_tie(self):
        deadline = self.available_start + timedelta(hours=2)
        low_energy = self.make_task(1, "Low energy", 30, deadline, energy_level="low")
        high_energy = self.make_task(2, "High energy", 30, deadline, energy_level="high")
        medium_energy = self.make_task(3, "Medium energy", 30, deadline, energy_level="medium")

        result = self.engine.generate_schedule(
            [low_energy, high_energy, medium_energy], self.available_start, self.available_end, "medium"
        )

        self.assertEqual(result.schedule[0].task_id, 3)

    def test_high_user_energy_prefers_high_energy_task_when_other_rules_tie(self):
        deadline = self.available_start + timedelta(hours=2)
        low_energy = self.make_task(1, "Low energy", 30, deadline, energy_level="low")
        high_energy = self.make_task(2, "High energy", 30, deadline, energy_level="high")

        result = self.engine.generate_schedule(
            [low_energy, high_energy], self.available_start, self.available_end, "high"
        )

        self.assertEqual([item.task_id for item in result.schedule], [2, 1])

    def test_urgent_deadline_beats_energy_compatibility(self):
        urgent_high_energy = self.make_task(
            1, "Urgent", 30, self.available_start + timedelta(hours=1), energy_level="high"
        )
        later_low_energy = self.make_task(
            2, "Later", 30, self.available_start + timedelta(days=2), energy_level="low"
        )

        result = self.engine.generate_schedule(
            [later_low_energy, urgent_high_energy], self.available_start, self.available_end, "low"
        )

        self.assertEqual(result.schedule[0].task_id, 1)

    def test_priority_beats_energy_compatibility_when_deadline_matches(self):
        deadline = self.available_start + timedelta(hours=2)
        high_priority = self.make_task(
            1, "High priority", 30, deadline, priority="high", energy_level="high"
        )
        low_priority = self.make_task(
            2, "Low priority", 30, deadline, priority="low", energy_level="low"
        )

        result = self.engine.generate_schedule(
            [low_priority, high_priority], self.available_start, self.available_end, "low"
        )

        self.assertEqual(result.schedule[0].task_id, 1)

    def test_omitted_user_energy_preserves_existing_tie_breaker(self):
        deadline = self.available_start + timedelta(hours=2)
        high_energy = self.make_task(1, "First by ID", 30, deadline, energy_level="high")
        low_energy = self.make_task(2, "Second by ID", 30, deadline, energy_level="low")

        result = self.engine.generate_schedule(
            [high_energy, low_energy], self.available_start, self.available_end
        )

        self.assertEqual([item.task_id for item in result.schedule], [1, 2])

    def test_overload_detection_still_works_with_user_energy(self):
        task = self.make_task(
            1, "Too long", 121, self.available_start + timedelta(hours=1), energy_level="low"
        )

        result = self.engine.generate_schedule(
            [task], self.available_start, self.available_end, "low"
        )

        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)

    def test_bad_day_false_preserves_normal_planning_behavior(self):
        tasks = [
            self.make_task(1, "First", 30, self.available_start + timedelta(hours=1)),
            self.make_task(2, "Second", 30, self.available_start + timedelta(hours=2)),
        ]

        normal_result = self.engine.generate_schedule(tasks, self.available_start, self.available_end)
        bad_day_false_result = self.engine.generate_schedule(
            tasks, self.available_start, self.available_end, bad_day=False
        )

        self.assertEqual(normal_result.schedule, bad_day_false_result.schedule)
        self.assertFalse(bad_day_false_result.bad_day)

    def test_bad_day_reduces_normal_workload(self):
        available_end = self.available_start + timedelta(minutes=100)
        tasks = [
            self.make_task(1, "One", 30, self.available_start + timedelta(days=2)),
            self.make_task(2, "Two", 30, self.available_start + timedelta(days=3)),
            self.make_task(3, "Three", 30, self.available_start + timedelta(days=4)),
        ]

        normal_result = self.engine.generate_schedule(tasks, self.available_start, available_end)
        bad_day_result = self.engine.generate_schedule(
            tasks, self.available_start, available_end, bad_day=True
        )

        self.assertEqual(len(normal_result.schedule), 3)
        self.assertEqual(len(bad_day_result.schedule), 2)
        self.assertTrue(bad_day_result.bad_day)

    def test_overdue_task_is_protected_beyond_bad_day_target(self):
        available_end = self.available_start + timedelta(minutes=100)
        overdue = self.make_task(1, "Overdue", 80, self.available_start - timedelta(minutes=1))
        future = self.make_task(2, "Future", 30, self.available_start + timedelta(days=2))

        result = self.engine.generate_schedule(
            [future, overdue], self.available_start, available_end, bad_day=True
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertEqual(result.schedule[0].scheduled_end, self.available_start + timedelta(minutes=80))

    def test_due_soon_task_is_protected_in_bad_day_mode(self):
        available_end = self.available_start + timedelta(minutes=100)
        due_soon = self.make_task(1, "Due soon", 70, self.available_start + timedelta(hours=2))
        future = self.make_task(2, "Future", 30, self.available_start + timedelta(days=2), "high")

        result = self.engine.generate_schedule(
            [future, due_soon], self.available_start, available_end, bad_day=True
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])

    def test_low_priority_future_task_is_deprioritized_in_bad_day_mode(self):
        available_end = self.available_start + timedelta(minutes=50)
        high_priority = self.make_task(
            1, "High priority", 30, self.available_start + timedelta(days=2), "high"
        )
        low_priority = self.make_task(
            2, "Low priority", 30, self.available_start + timedelta(days=2), "low"
        )

        result = self.engine.generate_schedule(
            [low_priority, high_priority], self.available_start, available_end, bad_day=True
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])

    def test_energy_preference_still_works_for_comparable_bad_day_tasks(self):
        available_end = self.available_start + timedelta(minutes=50)
        high_energy = self.make_task(
            1, "High energy", 30, self.available_start + timedelta(days=2), energy_level="high"
        )
        low_energy = self.make_task(
            2, "Low energy", 30, self.available_start + timedelta(days=2), energy_level="low"
        )

        result = self.engine.generate_schedule(
            [high_energy, low_energy], self.available_start, available_end, "low", bad_day=True
        )

        self.assertEqual([item.task_id for item in result.schedule], [2])

    def test_bad_day_reports_overload_when_protected_work_cannot_fit(self):
        overdue = self.make_task(1, "Too long overdue", 121, self.available_start - timedelta(minutes=1))

        result = self.engine.generate_schedule(
            [overdue], self.available_start, self.available_end, bad_day=True
        )

        self.assertEqual(result.schedule, [])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)


if __name__ == "__main__":
    unittest.main()
