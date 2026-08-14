from dataclasses import dataclass
from datetime import date, timedelta

from app.models.task import Task
from app.models.task_history import TaskHistory


@dataclass(frozen=True)
class ProgressResult:
    completed_tasks: int
    completed_minutes: int
    estimated_completed_minutes: int
    completion_rate: float
    current_streak_days: int
    progress_level: int
    progress_percent: float


class ProgressService:
    """Calculates positive, read-only progress statistics."""

    def calculate(
        self,
        tasks: list[Task],
        history_records: list[TaskHistory],
        current_date: date,
    ) -> ProgressResult:
        completed_tasks = [task for task in tasks if task.completed]
        completed_count = len(completed_tasks)
        completed_minutes = sum(
            task.actual_duration_minutes
            for task in completed_tasks
            if task.actual_duration_minutes is not None
        )
        estimated_completed_minutes = sum(task.duration_minutes for task in completed_tasks)
        completion_rate = 0.0 if not tasks else completed_count / len(tasks) * 100
        completion_dates = {
            record.timestamp.date()
            for record in history_records
            if record.event_type == "completed" and record.timestamp.date() <= current_date
        }

        current_streak_days = 0
        streak_date = current_date
        while streak_date in completion_dates:
            current_streak_days += 1
            streak_date -= timedelta(days=1)

        progress_level, progress_percent = self._progress_level(completed_count)
        return ProgressResult(
            completed_tasks=completed_count,
            completed_minutes=completed_minutes,
            estimated_completed_minutes=estimated_completed_minutes,
            completion_rate=completion_rate,
            current_streak_days=current_streak_days,
            progress_level=progress_level,
            progress_percent=progress_percent,
        )

    def _progress_level(self, completed_tasks: int) -> tuple[int, float]:
        if completed_tasks < 5:
            return 1, completed_tasks / 5 * 100
        if completed_tasks < 10:
            return 2, (completed_tasks - 5) / 5 * 100
        if completed_tasks < 20:
            return 3, (completed_tasks - 10) / 10 * 100
        if completed_tasks < 35:
            return 4, (completed_tasks - 20) / 15 * 100
        return 5, 100.0
