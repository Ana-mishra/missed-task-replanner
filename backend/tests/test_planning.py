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
            self.make_task(
                1,
                "First",
                30,
                self.available_start + timedelta(hours=1),
            ),
            self.make_task(
                2,
                "Second",
                45,
                self.available_start + timedelta(hours=2),
            ),
        ]

        result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            self.available_end,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1, 2],
        )
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)
        self.assertEqual(
            result.schedule[0].scheduled_start,
            self.available_start,
        )
        self.assertEqual(
            result.schedule[0].scheduled_end,
            self.available_start + timedelta(minutes=30),
        )
        self.assertEqual(
            result.schedule[1].scheduled_start,
            result.schedule[0].scheduled_end,
        )

    def test_incremental_schedule_keeps_existing_slots_when_new_work_is_last(self):
        first = self.make_task(
            1,
            "First",
            30,
            self.available_start + timedelta(hours=1),
        )
        second = self.make_task(
            2,
            "Second",
            30,
            self.available_start + timedelta(hours=2),
        )
        added = self.make_task(
            3,
            "Added",
            30,
            self.available_start + timedelta(hours=3),
        )

        first.scheduled_start = self.available_start
        first.scheduled_end = self.available_start + timedelta(minutes=30)

        second.scheduled_start = first.scheduled_end
        second.scheduled_end = second.scheduled_start + timedelta(minutes=30)

        result = self.engine.generate_schedule(
            [first, second, added],
            self.available_start,
            self.available_end,
            preserve_persisted_slots=True,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1, 2, 3],
        )
        self.assertEqual(
            result.schedule[0].scheduled_start,
            first.scheduled_start,
        )
        self.assertEqual(
            result.schedule[1].scheduled_start,
            second.scheduled_start,
        )
        self.assertEqual(
            result.schedule[2].scheduled_start,
            second.scheduled_end,
        )

    def test_incremental_schedule_shifts_only_later_slots_after_an_insertion(self):
        first = self.make_task(
            1,
            "First",
            30,
            self.available_start + timedelta(minutes=45),
        )
        second = self.make_task(
            2,
            "Second",
            30,
            self.available_start + timedelta(hours=2),
        )
        inserted = self.make_task(
            3,
            "Inserted",
            30,
            self.available_start + timedelta(hours=1),
        )

        first.scheduled_start = self.available_start
        first.scheduled_end = self.available_start + timedelta(minutes=30)

        second.scheduled_start = first.scheduled_end
        second.scheduled_end = second.scheduled_start + timedelta(minutes=30)

        result = self.engine.generate_schedule(
            [first, second, inserted],
            self.available_start,
            self.available_end,
            preserve_persisted_slots=True,
        )

        schedule = {
            item.task_id: item
            for item in result.schedule
        }

        self.assertEqual(
            schedule[first.id].scheduled_start,
            first.scheduled_start,
        )
        self.assertEqual(
            schedule[inserted.id].scheduled_start,
            first.scheduled_end,
        )
        self.assertEqual(
            schedule[second.id].scheduled_start,
            schedule[inserted.id].scheduled_end,
        )

    def test_incremental_schedule_preserves_future_slots_after_overdue_task_when_no_conflict(
        self,
    ):
        overdue = self.make_task(
            1,
            "Overdue",
            10,
            self.available_start - timedelta(hours=1),
        )
        future = self.make_task(
            2,
            "Future",
            30,
            self.available_start + timedelta(hours=2),
        )
        added = self.make_task(
            3,
            "Added",
            30,
            self.available_start + timedelta(hours=3),
        )

        overdue.scheduled_start = (
            self.available_start - timedelta(minutes=10)
        )
        overdue.scheduled_end = self.available_start

        future.scheduled_start = (
            self.available_start + timedelta(minutes=20)
        )
        future.scheduled_end = (
            future.scheduled_start + timedelta(minutes=30)
        )

        result = self.engine.generate_schedule(
            [overdue, future, added],
            self.available_start,
            self.available_end,
            preserve_persisted_slots=True,
        )

        schedule = {
            item.task_id: item
            for item in result.schedule
        }

        self.assertEqual(
            schedule[overdue.id].scheduled_start,
            self.available_start,
        )

        self.assertEqual(
            schedule[future.id].scheduled_start,
            future.scheduled_start,
        )

        self.assertEqual(
            schedule[added.id].scheduled_start,
            future.scheduled_end,
        )

    def test_incremental_schedule_replans_a_fully_elapsed_slot_from_the_reference_time(
        self,
    ):
        stale = self.make_task(
            1,
            "Stale",
            30,
            self.available_start + timedelta(hours=1),
        )
        future = self.make_task(
            2,
            "Future",
            30,
            self.available_start + timedelta(hours=2),
        )
        stale.scheduled_start = self.available_start - timedelta(hours=1)
        stale.scheduled_end = self.available_start - timedelta(minutes=30)
        future.scheduled_start = self.available_start + timedelta(minutes=30)
        future.scheduled_end = self.available_start + timedelta(hours=1)

        result = self.engine.generate_schedule(
            [stale, future],
            self.available_start,
            self.available_end,
            preserve_persisted_slots=True,
        )
        schedule = {item.task_id: item for item in result.schedule}

        self.assertEqual(schedule[stale.id].scheduled_start, self.available_start)
        self.assertGreaterEqual(schedule[stale.id].scheduled_start, self.available_start)
        self.assertEqual(schedule[future.id].scheduled_start, future.scheduled_start)

    def test_incremental_schedule_new_task_at_bottom_does_not_reschedule_existing_tasks_after_plan_started(
        self,
    ):
        current_time = datetime(2026, 8, 20, 9, 40)

        lilu = self.make_task(
            1,
            "lilu",
            30,
            current_time + timedelta(hours=2),
        )
        hehe = self.make_task(
            2,
            "hehe",
            30,
            current_time + timedelta(hours=3),
        )
        hbbhh = self.make_task(
            3,
            "hbbhh",
            30,
            current_time + timedelta(hours=4),
        )
        added = self.make_task(
            4,
            "hi",
            30,
            current_time + timedelta(hours=5),
        )

        lilu.scheduled_start = datetime(2026, 8, 20, 9, 29)
        lilu.scheduled_end = datetime(2026, 8, 20, 9, 59)

        hehe.scheduled_start = datetime(2026, 8, 20, 9, 59)
        hehe.scheduled_end = datetime(2026, 8, 20, 10, 29)

        hbbhh.scheduled_start = datetime(2026, 8, 20, 10, 29)
        hbbhh.scheduled_end = datetime(2026, 8, 20, 10, 59)

        result = self.engine.generate_schedule(
            [lilu, hehe, hbbhh, added],
            current_time,
            datetime(2026, 8, 20, 12, 0),
            preserve_persisted_slots=True,
        )

        schedule = {
            item.task_id: item
            for item in result.schedule
        }

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1, 2, 3, 4],
        )

        self.assertEqual(
            schedule[hehe.id].scheduled_start,
            datetime(2026, 8, 20, 9, 59),
        )

        self.assertEqual(
            schedule[hbbhh.id].scheduled_start,
            datetime(2026, 8, 20, 10, 29),
        )

        self.assertEqual(
            schedule[added.id].scheduled_start,
            datetime(2026, 8, 20, 10, 59),
        )

    def test_incremental_schedule_reassigns_an_edited_task(self):
        task = self.make_task(
            1,
            "Edited",
            45,
            self.available_start + timedelta(hours=1),
        )

        task.scheduled_start = self.available_start
        task.scheduled_end = self.available_start + timedelta(minutes=30)
        task.schedule_needs_refresh = True
        task.schedule_refresh_reason = "edited"

        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            preserve_persisted_slots=True,
        )

        self.assertEqual(
            result.schedule[0].scheduled_start,
            self.available_start,
        )
        self.assertEqual(
            result.schedule[0].scheduled_end,
            self.available_start + timedelta(minutes=45),
        )

    def test_deadline_ordering_places_overdue_then_closest_deadline(self):
        tasks = [
            self.make_task(
                1,
                "Later",
                10,
                self.available_start + timedelta(days=2),
                "high",
            ),
            self.make_task(
                2,
                "Overdue",
                10,
                self.available_start - timedelta(minutes=1),
                "low",
            ),
            self.make_task(
                3,
                "Soon",
                10,
                self.available_start + timedelta(hours=1),
                "medium",
            ),
        ]

        result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            self.available_end,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2, 3, 1],
        )

    def test_large_task_that_does_not_fit_allows_later_shorter_task(self):
        large_task = self.make_task(
            1,
            "Too long",
            121,
            self.available_start + timedelta(hours=1),
        )
        short_task = self.make_task(
            2,
            "Short task",
            30,
            self.available_start + timedelta(hours=2),
        )

        result = self.engine.generate_schedule(
            [large_task, short_task],
            self.available_start,
            self.available_end,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2],
        )
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)

    def test_completed_tasks_are_ignored(self):
        completed_task = self.make_task(
            1,
            "Done",
            121,
            self.available_start,
            completed=True,
        )
        pending_task = self.make_task(
            2,
            "Pending",
            30,
            self.available_start + timedelta(hours=1),
        )

        result = self.engine.generate_schedule(
            [completed_task, pending_task],
            self.available_start,
            self.available_end,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2],
        )
        self.assertFalse(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 0)

    def test_low_user_energy_prefers_low_energy_task_when_other_rules_tie(self):
        deadline = self.available_start + timedelta(hours=2)

        high_energy = self.make_task(
            1,
            "High energy",
            30,
            deadline,
            energy_level="high",
        )
        low_energy = self.make_task(
            2,
            "Low energy",
            30,
            deadline,
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [high_energy, low_energy],
            self.available_start,
            self.available_end,
            "low",
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2, 1],
        )

    def test_medium_user_energy_prefers_medium_energy_task_when_other_rules_tie(
        self,
    ):
        deadline = self.available_start + timedelta(hours=2)

        low_energy = self.make_task(
            1,
            "Low energy",
            30,
            deadline,
            energy_level="low",
        )
        high_energy = self.make_task(
            2,
            "High energy",
            30,
            deadline,
            energy_level="high",
        )
        medium_energy = self.make_task(
            3,
            "Medium energy",
            30,
            deadline,
            energy_level="medium",
        )

        result = self.engine.generate_schedule(
            [low_energy, high_energy, medium_energy],
            self.available_start,
            self.available_end,
            "medium",
        )

        self.assertEqual(
            result.schedule[0].task_id,
            3,
        )

    def test_high_user_energy_prefers_high_energy_task_when_other_rules_tie(
        self,
    ):
        deadline = self.available_start + timedelta(hours=2)

        low_energy = self.make_task(
            1,
            "Low energy",
            30,
            deadline,
            energy_level="low",
        )
        high_energy = self.make_task(
            2,
            "High energy",
            30,
            deadline,
            energy_level="high",
        )

        result = self.engine.generate_schedule(
            [low_energy, high_energy],
            self.available_start,
            self.available_end,
            "high",
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2, 1],
        )

    def test_urgent_deadline_beats_energy_compatibility(self):
        urgent_high_energy = self.make_task(
            1,
            "Urgent",
            30,
            self.available_start + timedelta(hours=1),
            energy_level="high",
        )
        later_low_energy = self.make_task(
            2,
            "Later",
            30,
            self.available_start + timedelta(days=2),
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [later_low_energy, urgent_high_energy],
            self.available_start,
            self.available_end,
            "low",
        )

        self.assertEqual(
            result.schedule[0].task_id,
            1,
        )

    def test_priority_beats_energy_compatibility_when_deadline_matches(self):
        deadline = self.available_start + timedelta(hours=2)

        high_priority = self.make_task(
            1,
            "High priority",
            30,
            deadline,
            priority="high",
            energy_level="high",
        )
        low_priority = self.make_task(
            2,
            "Low priority",
            30,
            deadline,
            priority="low",
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [low_priority, high_priority],
            self.available_start,
            self.available_end,
            "low",
        )

        self.assertEqual(
            result.schedule[0].task_id,
            1,
        )

    def test_omitted_user_energy_preserves_existing_tie_breaker(self):
        deadline = self.available_start + timedelta(hours=2)

        high_energy = self.make_task(
            1,
            "First by ID",
            30,
            deadline,
            energy_level="high",
        )
        low_energy = self.make_task(
            2,
            "Second by ID",
            30,
            deadline,
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [high_energy, low_energy],
            self.available_start,
            self.available_end,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1, 2],
        )

    def test_overload_detection_still_works_with_user_energy(self):
        task = self.make_task(
            1,
            "Too long",
            121,
            self.available_start + timedelta(hours=1),
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            "low",
        )

        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)

    def test_bad_day_false_preserves_normal_planning_behavior(self):
        tasks = [
            self.make_task(
                1,
                "First",
                30,
                self.available_start + timedelta(hours=1),
            ),
            self.make_task(
                2,
                "Second",
                30,
                self.available_start + timedelta(hours=2),
            ),
        ]

        normal_result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            self.available_end,
        )

        bad_day_false_result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            self.available_end,
            bad_day=False,
        )

        self.assertEqual(
            normal_result.schedule,
            bad_day_false_result.schedule,
        )
        self.assertFalse(bad_day_false_result.bad_day)

    def test_bad_day_reduces_normal_workload(self):
        available_end = self.available_start + timedelta(minutes=100)

        tasks = [
            self.make_task(
                1,
                "One",
                30,
                self.available_start + timedelta(days=2),
            ),
            self.make_task(
                2,
                "Two",
                30,
                self.available_start + timedelta(days=3),
            ),
            self.make_task(
                3,
                "Three",
                30,
                self.available_start + timedelta(days=4),
            ),
        ]

        normal_result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            available_end,
        )

        bad_day_result = self.engine.generate_schedule(
            tasks,
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual(len(normal_result.schedule), 3)
        self.assertEqual(len(bad_day_result.schedule), 2)
        self.assertTrue(bad_day_result.bad_day)

    def test_overdue_task_is_protected_beyond_bad_day_target(self):
        available_end = self.available_start + timedelta(minutes=100)

        overdue = self.make_task(
            1,
            "Overdue",
            80,
            self.available_start - timedelta(minutes=1),
        )
        future = self.make_task(
            2,
            "Future",
            30,
            self.available_start + timedelta(days=2),
        )

        result = self.engine.generate_schedule(
            [future, overdue],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1],
        )
        self.assertEqual(
            result.schedule[0].scheduled_end,
            self.available_start + timedelta(minutes=80),
        )

    def test_due_soon_task_is_protected_in_bad_day_mode(self):
        available_end = self.available_start + timedelta(minutes=100)

        due_soon = self.make_task(
            1,
            "Due soon",
            70,
            self.available_start + timedelta(hours=2),
        )
        future = self.make_task(
            2,
            "Future",
            30,
            self.available_start + timedelta(days=2),
            "high",
        )

        result = self.engine.generate_schedule(
            [future, due_soon],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1],
        )

    def test_priority_breaks_ties_between_same_energy_movable_tasks(self):
        available_end = self.available_start + timedelta(minutes=50)

        high_priority = self.make_task(
            1,
            "High priority",
            30,
            self.available_start + timedelta(days=2),
            priority="high",
            energy_level="low",
        )
        low_priority = self.make_task(
            2,
            "Low priority",
            30,
            self.available_start + timedelta(days=2),
            priority="low",
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [low_priority, high_priority],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1],
        )

    def test_bad_day_protects_due_tomorrow_high_energy_work_before_movable_low_energy_work(self):
        available_end = self.available_start + timedelta(minutes=100)
        due_tomorrow = self.make_task(
            1,
            "Due tomorrow",
            90,
            self.available_start + timedelta(days=1, hours=8),
            priority="high",
            energy_level="high",
        )
        distant_low_energy = self.make_task(
            2,
            "Low energy later",
            30,
            self.available_start + timedelta(days=5),
            priority="medium",
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [distant_low_energy, due_tomorrow],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertEqual(result.unscheduled_minutes, 30)

    def test_bad_day_prefers_low_energy_movable_work_before_higher_energy_work(self):
        available_end = self.available_start + timedelta(minutes=50)
        high_energy = self.make_task(
            1,
            "High energy later",
            30,
            self.available_start + timedelta(days=4),
            priority="high",
            energy_level="high",
        )
        low_energy = self.make_task(
            2,
            "Low energy later",
            30,
            self.available_start + timedelta(days=4),
            priority="low",
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [high_energy, low_energy],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual([item.task_id for item in result.schedule], [2])

    def test_bad_day_protected_work_can_exceed_preferred_capacity_target(self):
        available_end = self.available_start + timedelta(minutes=120)
        protected = self.make_task(
            1,
            "Deadline tomorrow",
            90,
            self.available_start + timedelta(days=1),
            priority="high",
            energy_level="high",
        )

        result = self.engine.generate_schedule(
            [protected],
            self.available_start,
            available_end,
            bad_day=True,
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertEqual(result.schedule[0].scheduled_end, available_end - timedelta(minutes=30))

    def test_energy_preference_still_works_for_comparable_bad_day_tasks(
        self,
    ):
        available_end = self.available_start + timedelta(minutes=50)

        high_energy = self.make_task(
            1,
            "High energy",
            30,
            self.available_start + timedelta(days=2),
            energy_level="high",
        )
        low_energy = self.make_task(
            2,
            "Low energy",
            30,
            self.available_start + timedelta(days=2),
            energy_level="low",
        )

        result = self.engine.generate_schedule(
            [high_energy, low_energy],
            self.available_start,
            available_end,
            "low",
            bad_day=True,
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2],
        )

    def test_bad_day_reports_overload_when_protected_work_cannot_fit(self):
        overdue = self.make_task(
            1,
            "Too long overdue",
            121,
            self.available_start - timedelta(minutes=1),
        )

        result = self.engine.generate_schedule(
            [overdue],
            self.available_start,
            self.available_end,
            bad_day=True,
        )

        self.assertEqual(result.schedule, [])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 121)

    def test_reason_kept_because_deadline_is_today(self):
        task = self.make_task(
            1,
            "Due today",
            30,
            self.available_start + timedelta(hours=1),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            bad_day=True,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline is today", result.schedule[0].reason)

    def test_reason_kept_because_deadline_is_tomorrow(self):
        task = self.make_task(
            1,
            "Due tomorrow",
            30,
            self.available_start + timedelta(days=1),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            bad_day=True,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline is tomorrow", result.schedule[0].reason)

    def test_reason_prioritized_energy_match_in_bad_day(self):
        task = self.make_task(
            1,
            "Low energy task",
            30,
            self.available_start + timedelta(days=2),
            energy_level="low",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            bad_day=True,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("matches your current energy", result.schedule[0].reason)

    def test_reason_within_reduced_workload_high_energy_not_protected(self):
        task = self.make_task(
            1,
            "High energy flexible",
            30,
            self.available_start + timedelta(days=5),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            bad_day=True,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("reduced workload", result.schedule[0].reason)

    def test_reason_scheduled_by_deadline_and_priority_normal_day(self):
        task = self.make_task(
            1,
            "Flexible task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="medium",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            user_energy_level="medium",
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline", result.schedule[0].reason.lower())

    def test_reason_scheduled_by_deadline_and_priority_normal_day(self):
        task = self.make_task(
            1,
            "Flexible task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            user_energy_level="low",
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline", result.schedule[0].reason.lower())
        self.assertIn("priority", result.schedule[0].reason.lower())

    def test_reason_keeps_close_deadline_normal_day(self):
        task = self.make_task(
            1,
            "Close deadline",
            30,
            self.available_start + timedelta(hours=1),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline is today", result.schedule[0].reason)

    def test_reason_no_energy_claim_without_user_energy_normal_day(self):
        task = self.make_task(
            1,
            "Low energy task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="low",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertEqual(
            result.schedule[0].reason, "Scheduled by deadline and priority."
        )

    def test_reason_energy_match_with_explicit_user_energy_normal_day(self):
        task = self.make_task(
            1,
            "Low energy task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="low",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            user_energy_level="low",
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertEqual(
            result.schedule[0].reason,
            "Prioritized because it matches your energy.",
        )

    def test_reason_energy_mismatch_with_explicit_user_energy_normal_day(self):
        task = self.make_task(
            1,
            "High energy task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="high",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            user_energy_level="low",
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertEqual(
            result.schedule[0].reason, "Scheduled by deadline and priority."
        )

    def test_reason_bad_day_energy_match_unchanged(self):
        task = self.make_task(
            1,
            "Low energy task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="low",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
            bad_day=True,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertEqual(
            result.schedule[0].reason,
            "Prioritized because it matches your current energy.",
        )

    def test_reason_deadline_protection_without_user_energy_normal_day(self):
        task = self.make_task(
            1,
            "Due today",
            30,
            self.available_start + timedelta(hours=1),
            energy_level="low",
        )
        result = self.engine.generate_schedule(
            [task],
            self.available_start,
            self.available_end,
        )
        self.assertEqual(len(result.schedule), 1)
        self.assertIn("deadline is today", result.schedule[0].reason)

    def test_bad_day_protected_count_and_capacity(self):
        protected = self.make_task(
            1,
            "Protected task",
            30,
            self.available_start + timedelta(hours=1),
        )
        flexible = self.make_task(
            2,
            "Flexible task",
            30,
            self.available_start + timedelta(days=5),
            energy_level="low",
        )
        available_end = self.available_start + timedelta(hours=2)
        result = self.engine.generate_schedule(
            [protected, flexible],
            self.available_start,
            available_end,
            bad_day=True,
        )
        self.assertGreaterEqual(len(result.schedule), 1)


if __name__ == "__main__":
    unittest.main()
