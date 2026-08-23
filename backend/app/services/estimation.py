from dataclasses import dataclass

from app.models.task import Task


@dataclass(frozen=True)
class EstimationResult:
    completed_tasks: int
    estimated_minutes: int
    actual_minutes: int
    total_difference_minutes: int
    average_difference_minutes: float
    average_accuracy_percent: float
    tendency: str


class EstimationService:
    """Calculates estimation accuracy from completed tasks."""

    def calculate(self, tasks: list[Task]) -> EstimationResult:
        eligible_tasks = [
            task
            for task in tasks
            if task.completed
            and task.actual_duration_minutes is not None
            and task.duration_minutes > 0
        ]

        if not eligible_tasks:
            return EstimationResult(
                completed_tasks=0,
                estimated_minutes=0,
                actual_minutes=0,
                total_difference_minutes=0,
                average_difference_minutes=0.0,
                average_accuracy_percent=0.0,
                tendency="insufficient_data",
            )

        estimated_minutes = sum(task.duration_minutes for task in eligible_tasks)
        actual_minutes = sum(task.actual_duration_minutes for task in eligible_tasks)
        total_difference_minutes = actual_minutes - estimated_minutes
        completed_tasks = len(eligible_tasks)

        if max(estimated_minutes, actual_minutes) > 0:
            average_accuracy_percent = (
                min(estimated_minutes, actual_minutes)
                / max(estimated_minutes, actual_minutes)
                * 100
            )
        else:
            average_accuracy_percent = 0.0

        if total_difference_minutes > 0:
            tendency = "underestimate"
        elif total_difference_minutes < 0:
            tendency = "overestimate"
        else:
            tendency = "accurate"

        return EstimationResult(
            completed_tasks=completed_tasks,
            estimated_minutes=estimated_minutes,
            actual_minutes=actual_minutes,
            total_difference_minutes=total_difference_minutes,
            average_difference_minutes=total_difference_minutes / completed_tasks,
            average_accuracy_percent=average_accuracy_percent,
            tendency=tendency,
        )
