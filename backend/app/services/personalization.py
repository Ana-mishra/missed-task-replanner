from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services.estimation import EstimationService
from app.services.postponement import PostponementService


@dataclass(frozen=True)
class PersonalizationInsight:
    type: str
    message: str
    evidence_count: int
    confidence: str


class PersonalizationService:
    """Produces deterministic, evidence-backed insights without changing tasks."""

    estimation_minimum = 3
    postponement_threshold = 3
    pattern_minimum = 6
    meaningful_rate_difference = 0.20

    def analyze(
        self,
        tasks: list[Task],
        history_records: list[TaskHistory],
        current_time: datetime,
    ) -> list[PersonalizationInsight]:
        history = [record for record in history_records if record.timestamp <= current_time]
        insights: list[PersonalizationInsight] = []

        estimation_insight = self._estimation_insight(tasks)
        if estimation_insight is not None:
            insights.append(estimation_insight)

        insights.extend(self._postponement_insights(tasks, history))

        duration_insight = self._duration_postponement_insight(tasks, history)
        if duration_insight is not None:
            insights.append(duration_insight)

        energy_insight = self._energy_completion_insight(tasks, history)
        if energy_insight is not None:
            insights.append(energy_insight)

        return insights

    def _estimation_insight(self, tasks: list[Task]) -> PersonalizationInsight | None:
        eligible_tasks = [
            task
            for task in tasks
            if task.completed and task.actual_duration_minutes is not None and task.duration_minutes > 0
        ]
        if len(eligible_tasks) < self.estimation_minimum:
            return None

        result = EstimationService().calculate(eligible_tasks)
        underestimated_count = sum(
            task.actual_duration_minutes > task.duration_minutes for task in eligible_tasks
        )
        overestimated_count = sum(
            task.actual_duration_minutes < task.duration_minutes for task in eligible_tasks
        )
        if result.tendency == "underestimate":
            message = (
                "You tend to underestimate task duration in the available history "
                f"({underestimated_count} of {len(eligible_tasks)} tasks took longer than estimated)."
            )
        elif result.tendency == "overestimate":
            message = (
                "You tend to overestimate task duration in the available history "
                f"({overestimated_count} of {len(eligible_tasks)} tasks took less time than estimated)."
            )
        else:
            message = "Your task duration estimates are accurate in the available history."
        return PersonalizationInsight(
            type="estimation",
            message=message,
            evidence_count=len(eligible_tasks),
            confidence=self._estimation_confidence(len(eligible_tasks)),
        )

    def _postponement_insights(
        self, tasks: list[Task], history_records: list[TaskHistory]
    ) -> list[PersonalizationInsight]:
        history_by_task = defaultdict(list)
        for record in history_records:
            history_by_task[record.task_id].append(record)

        service = PostponementService()
        insights = []
        for task in sorted(tasks, key=lambda task: task.id):
            if task.completed:
                continue
            result = service.analyze(task.id, history_by_task.get(task.id, []), self.postponement_threshold)
            if result.needs_review:
                insights.append(
                    PersonalizationInsight(
                        type="postponement",
                        message=f"Task '{task.title}' has been postponed repeatedly and may need review.",
                        evidence_count=result.postponement_count,
                        confidence="high" if result.postponement_count >= 5 else "medium",
                    )
                )
        return insights

    def _duration_postponement_insight(
        self, tasks: list[Task], history_records: list[TaskHistory]
    ) -> PersonalizationInsight | None:
        usable_tasks = [task for task in tasks if task.duration_minutes > 0]
        if len(usable_tasks) < self.pattern_minimum:
            return None

        median_duration = self._median([task.duration_minutes for task in usable_tasks])
        shorter_tasks = [task for task in usable_tasks if task.duration_minutes < median_duration]
        longer_tasks = [task for task in usable_tasks if task.duration_minutes >= median_duration]
        if not shorter_tasks or not longer_tasks:
            return None

        history_by_task = defaultdict(list)
        for record in history_records:
            history_by_task[record.task_id].append(record)
        service = PostponementService()

        def postponement_rate(group: list[Task]) -> float:
            postponed = sum(
                service.analyze(task.id, history_by_task.get(task.id, [])).postponement_count > 0
                for task in group
            )
            return postponed / len(group)

        shorter_rate = postponement_rate(shorter_tasks)
        longer_rate = postponement_rate(longer_tasks)
        if longer_rate < shorter_rate + self.meaningful_rate_difference:
            return None

        return PersonalizationInsight(
            type="duration_pattern",
            message="Longer tasks appear to be postponed more often in the available history.",
            evidence_count=len(longer_tasks),
            confidence="medium",
        )

    def _energy_completion_insight(
        self, tasks: list[Task], history_records: list[TaskHistory]
    ) -> PersonalizationInsight | None:
        valid_energy_tasks = [task for task in tasks if task.energy_level in {"low", "medium", "high"}]
        if len(valid_energy_tasks) < self.pattern_minimum:
            return None

        completed_task_ids = {
            record.task_id for record in history_records if record.event_type == "completed"
        }
        tasks_by_energy = defaultdict(list)
        for task in valid_energy_tasks:
            tasks_by_energy[task.energy_level].append(task)
        if len(tasks_by_energy) < 2:
            return None

        rates = {
            energy_level: sum(task.id in completed_task_ids for task in energy_tasks) / len(energy_tasks)
            for energy_level, energy_tasks in tasks_by_energy.items()
        }
        best_energy = min(
            rates,
            key=lambda energy_level: (-rates[energy_level], {"low": 0, "medium": 1, "high": 2}[energy_level]),
        )
        other_rates = [rate for energy_level, rate in rates.items() if energy_level != best_energy]
        if rates[best_energy] < max(other_rates) + self.meaningful_rate_difference:
            return None

        return PersonalizationInsight(
            type="energy_pattern",
            message=(
                f"Tasks requiring {best_energy} energy have your highest completion rate "
                "in the available history."
            ),
            evidence_count=len(tasks_by_energy[best_energy]),
            confidence="medium",
        )

    @staticmethod
    def _median(values: list[int]) -> float:
        ordered_values = sorted(values)
        middle = len(ordered_values) // 2
        if len(ordered_values) % 2:
            return ordered_values[middle]
        return (ordered_values[middle - 1] + ordered_values[middle]) / 2

    @staticmethod
    def _estimation_confidence(evidence_count: int) -> str:
        if evidence_count >= 10:
            return "high"
        if evidence_count >= 5:
            return "medium"
        return "low"
