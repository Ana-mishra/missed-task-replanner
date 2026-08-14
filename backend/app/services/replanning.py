from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.task import Task
from app.services.planning import PlanningEngine, ScheduledTask


@dataclass(frozen=True)
class ReplanningResult:
    """The feasible schedule and any work that could not be placed."""

    schedule: list[ScheduledTask]
    is_overloaded: bool
    unscheduled_minutes: int


class ReplanningEngine:
    """Rebuilds the remaining schedule after a task is missed."""

    due_soon_window = timedelta(hours=24)

    def __init__(self):
        self.planning_engine = PlanningEngine()

    def generate_revised_schedule(
        self,
        tasks: list[Task],
        missed_task: Task,
        available_start: datetime,
        available_end: datetime,
    ) -> ReplanningResult:
        """Create a new schedule for incomplete work, including the missed task."""
        if available_end < available_start:
            raise ValueError("available_end must be after available_start")

        tasks_by_id = {task.id: task for task in tasks}
        tasks_by_id[missed_task.id] = missed_task
        incomplete_tasks = [task for task in tasks_by_id.values() if not task.completed]
        ordered_tasks = sorted(
            incomplete_tasks,
            key=lambda task: (
                self._urgency_group(task, available_start),
                task.deadline,
                self.planning_engine.priority_rank(task.priority),
                task.id,
            ),
        )

        current_time = available_start
        schedule: list[ScheduledTask] = []
        unscheduled_minutes = 0

        for task in ordered_tasks:
            if task.duration_minutes <= 0:
                continue

            scheduled_end = current_time + timedelta(minutes=task.duration_minutes)
            if scheduled_end > available_end:
                unscheduled_minutes += task.duration_minutes
                continue

            schedule.append(
                ScheduledTask(
                    task_id=task.id,
                    title=task.title,
                    scheduled_start=current_time,
                    scheduled_end=scheduled_end,
                )
            )
            current_time = scheduled_end

        return ReplanningResult(
            schedule=schedule,
            is_overloaded=unscheduled_minutes > 0,
            unscheduled_minutes=unscheduled_minutes,
        )

    def _urgency_group(self, task: Task, available_start: datetime) -> int:
        if task.deadline < available_start:
            return 0
        if task.deadline <= available_start + self.due_soon_window:
            return 1
        return 2
