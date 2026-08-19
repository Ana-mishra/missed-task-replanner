import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.replanning import ReplanningEngine


class ReplanningEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReplanningEngine()
        self.available_start = datetime(2026, 8, 20, 9, 0)
        self.available_end = datetime(2026, 8, 20, 12, 0)

    def make_task(
        self,
        task_id,
        title,
        duration,
        deadline,
        priority="medium",
        completed=False,
    ):
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
            1,
            "Missed task",
            30,
            self.available_start + timedelta(hours=1),
        )

        result = self.engine.generate_revised_schedule(
            [],
            missed_task,
            self.available_start,
            self.available_end,
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertFalse(result.is_overloaded)

    def test_missed_task_remains_unscheduled_when_it_does_not_fit_today(self):
        missed_task = self.make_task(
            1,
            "Missed task",
            180,
            self.available_start + timedelta(days=1),
        )

        available_end = self.available_start + timedelta(hours=1)

        result = self.engine.generate_revised_schedule(
            [],
            missed_task,
            self.available_start,
            available_end,
        )

        self.assertEqual(result.schedule, [])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 180)

    def test_next_day_planner_can_pick_up_missed_task(self):
        missed_task = self.make_task(
            1,
            "Missed task",
            60,
            self.available_start + timedelta(days=2),
        )

        # It cannot fit in today's remaining one hour because we give
        # today's window only 30 minutes.
        today_end = self.available_start + timedelta(minutes=30)

        replan_result = self.engine.generate_revised_schedule(
            [],
            missed_task,
            self.available_start,
            today_end,
        )

        self.assertEqual(replan_result.schedule, [])
        self.assertTrue(replan_result.is_overloaded)

        # The task is still unfinished, so the normal planner can consider
        # it when the next day is planned.
        next_day_start = self.available_start + timedelta(days=1)
        next_day_end = next_day_start + timedelta(hours=2)

        next_day_result = self.engine.planning_engine.generate_schedule(
            [missed_task],
            next_day_start,
            next_day_end,
        )

        self.assertEqual(
            [item.task_id for item in next_day_result.schedule],
            [missed_task.id],
        )    

    def test_urgent_tasks_remain_ahead_of_flexible_tasks(self):
        urgent_task = self.make_task(
            1,
            "Urgent",
            30,
            self.available_start + timedelta(hours=1),
            "low",
        )
        flexible_task = self.make_task(
            2,
            "Flexible",
            30,
            self.available_start + timedelta(days=3),
            "high",
        )
        missed_task = self.make_task(
            3,
            "Missed",
            30,
            self.available_start + timedelta(days=2),
            "medium",
        )

        result = self.engine.generate_revised_schedule(
            [urgent_task, flexible_task],
            missed_task,
            self.available_start,
            self.available_end,
        )

        self.assertEqual([item.task_id for item in result.schedule], [1, 3, 2])

    def test_new_task_with_closer_deadline_beats_missed_task(self):
        missed_task = self.make_task(
            1,
            "Missed task",
            60,
            self.available_start + timedelta(days=3),
            "medium",
        )

        new_task = self.make_task(
            2,
            "New urgent task",
            60,
            self.available_start + timedelta(hours=1),
            "medium",
        )

        result = self.engine.generate_revised_schedule(
            [new_task],
            missed_task,
            self.available_start,
            self.available_start + timedelta(hours=2),
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [2, 1],
        )

    def test_missed_task_with_closer_deadline_beats_new_task(self):
        missed_task = self.make_task(
            1,
            "Missed task",
            60,
            self.available_start + timedelta(hours=1),
            "medium",
        )

        new_task = self.make_task(
            2,
            "New task",
            60,
            self.available_start + timedelta(days=3),
            "medium",
        )

        result = self.engine.generate_revised_schedule(
            [new_task],
            missed_task,
            self.available_start,
            self.available_start + timedelta(hours=2),
        )

        self.assertEqual(
            [item.task_id for item in result.schedule],
            [1, 2],
        )    

    def test_overload_reports_unscheduled_work(self):
        urgent_task = self.make_task(
            1,
            "Urgent",
            90,
            self.available_start + timedelta(hours=1),
        )
        missed_task = self.make_task(
            2,
            "Missed",
            120,
            self.available_start + timedelta(days=1),
        )
        available_end = self.available_start + timedelta(hours=2)

        result = self.engine.generate_revised_schedule(
            [urgent_task],
            missed_task,
            self.available_start,
            available_end,
        )

        self.assertEqual([item.task_id for item in result.schedule], [1])
        self.assertTrue(result.is_overloaded)
        self.assertEqual(result.unscheduled_minutes, 120)

    def test_completed_tasks_are_excluded(self):
        completed_task = self.make_task(
            1,
            "Completed",
            30,
            self.available_start,
            completed=True,
        )
        missed_task = self.make_task(
            2,
            "Missed",
            30,
            self.available_start + timedelta(hours=1),
        )

        result = self.engine.generate_revised_schedule(
            [completed_task],
            missed_task,
            self.available_start,
            self.available_end,
        )

        self.assertEqual([item.task_id for item in result.schedule], [2])

    def test_replanning_recalculates_instead_of_appending_missed_task(self):
        flexible_task = self.make_task(
            1,
            "Flexible",
            30,
            self.available_start + timedelta(days=2),
            "high",
        )
        missed_task = self.make_task(
            2,
            "Missed overdue",
            30,
            self.available_start - timedelta(minutes=1),
            "low",
        )

        result = self.engine.generate_revised_schedule(
            [flexible_task],
            missed_task,
            self.available_start,
            self.available_end,
        )

        self.assertEqual([item.task_id for item in result.schedule], [2, 1])
        self.assertEqual(
            result.schedule[0].scheduled_start,
            self.available_start,
        )


if __name__ == "__main__":
    unittest.main()