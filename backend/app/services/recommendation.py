from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.planning import PlanningEngine


@dataclass(frozen=True)
class RecommendationResult:
    task: Task | None
    reason: str


class RecommendationEngine:
    """Selects one eligible task using deterministic scheduling rules."""

    due_soon_window = timedelta(hours=24)

    def __init__(self):
        self.planning_engine = PlanningEngine()

    def recommend(self, tasks: list[Task], current_time: datetime) -> RecommendationResult:
        eligible_tasks = [task for task in tasks if self._is_eligible(task, current_time)]
        if not eligible_tasks:
            return RecommendationResult(task=None, reason="No eligible task is available.")

        active_tasks = [task for task in eligible_tasks if self._is_currently_scheduled(task, current_time)]
        if active_tasks:
            task = min(active_tasks, key=lambda task: self._ranking_key(task, current_time))
            return RecommendationResult(task=task, reason="Task is currently scheduled.")

        task = min(eligible_tasks, key=lambda task: self._ranking_key(task, current_time))
        return RecommendationResult(task=task, reason=self._reason_for(task, current_time))

    def _is_eligible(self, task: Task, current_time: datetime) -> bool:
        if task.completed:
            return False
        if task.status != "missed":
            return True
        return task.scheduled_end is not None and task.scheduled_end >= current_time

    def _is_currently_scheduled(self, task: Task, current_time: datetime) -> bool:
        return (
            task.scheduled_start is not None
            and task.scheduled_end is not None
            and task.scheduled_start <= current_time <= task.scheduled_end
        )

    def _ranking_key(self, task: Task, current_time: datetime) -> tuple:
        return (
            self._urgency_group(task, current_time),
            task.deadline,
            self.planning_engine.priority_rank(task.priority),
            task.duration_minutes,
            task.id,
        )

    def _urgency_group(self, task: Task, current_time: datetime) -> int:
        if task.deadline < current_time:
            return 0
        if task.deadline <= current_time + self.due_soon_window:
            return 1
        return 2

    def _reason_for(self, task: Task, current_time: datetime) -> str:
        if task.deadline < current_time:
            return "Task is overdue."
        if task.deadline <= current_time + self.due_soon_window:
            return "Task is due within the next 24 hours."
        return "Task has the earliest deadline."
