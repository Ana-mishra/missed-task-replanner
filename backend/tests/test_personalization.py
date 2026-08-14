import unittest
from datetime import datetime, timedelta

from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services.personalization import PersonalizationService


class PersonalizationServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = PersonalizationService()
        self.now = datetime(2040, 1, 10, 12, 0)

    def task(
        self,
        task_id,
        *,
        duration=30,
        actual=None,
        completed=False,
        energy="medium",
    ):
        return Task(
            id=task_id,
            title=f"Task {task_id}",
            duration_minutes=duration,
            actual_duration_minutes=actual,
            deadline=self.now + timedelta(days=1),
            priority="medium",
            completed=completed,
            energy_level=energy,
        )

    def event(self, event_id, task_id, event_type, minutes=0):
        return TaskHistory(
            id=event_id,
            task_id=task_id,
            event_type=event_type,
            timestamp=self.now - timedelta(minutes=100) + timedelta(minutes=minutes),
        )

    def cycles(self, task_id, first_event_id, count, start_minutes=0):
        records = []
        for index in range(count):
            minute = start_minutes + index * 2
            records.extend(
                [
                    self.event(first_event_id + index * 2, task_id, "missed", minute),
                    self.event(first_event_id + index * 2 + 1, task_id, "replanned", minute + 1),
                ]
            )
        return records

    def insight_of_type(self, insights, insight_type):
        return next((insight for insight in insights if insight.type == insight_type), None)

    def test_no_data_returns_no_insights(self):
        self.assertEqual(self.service.analyze([], [], self.now), [])

    def test_fewer_than_three_estimates_do_not_create_estimation_insight(self):
        tasks = [self.task(1, actual=45, completed=True), self.task(2, actual=45, completed=True)]

        insights = self.service.analyze(tasks, [], self.now)

        self.assertIsNone(self.insight_of_type(insights, "estimation"))

    def test_estimation_insight_reports_underestimation(self):
        tasks = [self.task(task_id, actual=45, completed=True) for task_id in range(1, 4)]

        insight = self.insight_of_type(self.service.analyze(tasks, [], self.now), "estimation")

        self.assertIn("underestimate", insight.message)
        self.assertEqual(insight.evidence_count, 3)
        self.assertEqual(insight.confidence, "low")

    def test_estimation_insight_reports_overestimation(self):
        tasks = [self.task(task_id, duration=60, actual=30, completed=True) for task_id in range(1, 4)]

        insight = self.insight_of_type(self.service.analyze(tasks, [], self.now), "estimation")

        self.assertIn("overestimate", insight.message)

    def test_estimation_confidence_uses_evidence_thresholds(self):
        medium_tasks = [self.task(task_id, actual=45, completed=True) for task_id in range(1, 6)]
        high_tasks = [self.task(task_id, actual=45, completed=True) for task_id in range(1, 11)]

        medium = self.insight_of_type(self.service.analyze(medium_tasks, [], self.now), "estimation")
        high = self.insight_of_type(self.service.analyze(high_tasks, [], self.now), "estimation")

        self.assertEqual(medium.confidence, "medium")
        self.assertEqual(high.confidence, "high")

    def test_repeated_postponement_creates_review_insight(self):
        task = self.task(1)

        insight = self.insight_of_type(self.service.analyze([task], self.cycles(1, 1, 3), self.now), "postponement")

        self.assertEqual(insight.evidence_count, 3)
        self.assertEqual(insight.confidence, "medium")

    def test_postponement_below_threshold_creates_no_insight(self):
        task = self.task(1)

        insights = self.service.analyze([task], self.cycles(1, 1, 2), self.now)

        self.assertIsNone(self.insight_of_type(insights, "postponement"))

    def test_longer_tasks_postponed_more_often_creates_duration_insight(self):
        tasks = [self.task(index, duration=duration) for index, duration in enumerate([10, 20, 30, 60, 70, 80], 1)]
        records = self.cycles(4, 1, 1) + self.cycles(5, 3, 1) + self.cycles(6, 5, 1)

        insight = self.insight_of_type(self.service.analyze(tasks, records, self.now), "duration_pattern")

        self.assertEqual(insight.evidence_count, 3)
        self.assertIn("Longer tasks", insight.message)

    def test_insufficient_tasks_do_not_create_duration_insight(self):
        tasks = [self.task(index, duration=index * 10) for index in range(1, 6)]

        insights = self.service.analyze(tasks, self.cycles(5, 1, 1), self.now)

        self.assertIsNone(self.insight_of_type(insights, "duration_pattern"))

    def test_energy_pattern_uses_completion_history(self):
        tasks = [
            self.task(1, energy="medium"),
            self.task(2, energy="medium"),
            self.task(3, energy="low"),
            self.task(4, energy="low"),
            self.task(5, energy="high"),
            self.task(6, energy="high"),
        ]
        records = [self.event(1, 1, "completed"), self.event(2, 2, "completed")]

        insight = self.insight_of_type(self.service.analyze(tasks, records, self.now), "energy_pattern")

        self.assertEqual(insight.evidence_count, 2)
        self.assertIn("medium energy", insight.message)

    def test_insufficient_energy_data_creates_no_energy_insight(self):
        tasks = [self.task(index, energy="medium") for index in range(1, 6)]

        insights = self.service.analyze(tasks, [self.event(1, 1, "completed")], self.now)

        self.assertIsNone(self.insight_of_type(insights, "energy_pattern"))

    def test_deleted_and_future_history_are_ignored_safely(self):
        task = self.task(1)
        future_records = self.cycles(1, 1, 3, start_minutes=1)
        for record in future_records:
            record.timestamp = self.now + timedelta(days=1)
        deleted_task_records = self.cycles(999, 7, 3)

        insights = self.service.analyze([task], future_records + deleted_task_records, self.now)

        self.assertIsNone(self.insight_of_type(insights, "postponement"))

    def test_insights_are_deterministic(self):
        tasks = [self.task(task_id, actual=45, completed=True) for task_id in range(1, 4)]
        records = self.cycles(4, 1, 3)
        tasks.append(self.task(4))

        first = self.service.analyze(tasks, records, self.now)
        second = self.service.analyze(tasks, records, self.now)

        self.assertEqual(first, second)
