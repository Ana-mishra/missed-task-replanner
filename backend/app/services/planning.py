from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.task import Task


@dataclass(frozen=True)
class ScheduledTask:
    """One task placed in the available time window."""

    task_id: int
    title: str
    scheduled_start: datetime
    scheduled_end: datetime


@dataclass(frozen=True)
class PlanningResult:
    """The feasible schedule and work that did not fit in the time window."""

    schedule: list[ScheduledTask]
    is_overloaded: bool
    unscheduled_minutes: int
    bad_day: bool = False


class PlanningEngine:
    """Creates a basic, rule-based task schedule."""

    _priority_order = {"high": 0, "medium": 1, "low": 2}
    _energy_order = {"low": 0, "medium": 1, "high": 2}
    due_soon_window = timedelta(hours=24)

    @classmethod
    def priority_rank(cls, priority: str) -> int:
        """Return a consistent sort rank for a task priority."""
        return cls._priority_order.get(priority.lower(), 3)

    def generate_schedule(
        self,
        tasks: list[Task],
        available_start: datetime,
        available_end: datetime,
        user_energy_level: str | None = None,
        bad_day: bool = False,
    ) -> PlanningResult:
        """Schedule unfinished tasks in deadline and priority order.

        A task is overdue when its deadline is before the available start time.
        Tasks that do not fit are skipped, allowing later shorter tasks to use
        any remaining time.
        """
        if available_end < available_start:
            raise ValueError("available_end must be after available_start")

        unfinished_tasks = [task for task in tasks if not task.completed]
        ordered_tasks = sorted(
            unfinished_tasks,
            key=lambda task: (
                task.deadline >= available_start,
                task.deadline,
                self.priority_rank(task.priority),
                self.energy_compatibility_rank(task.energy_level, user_energy_level),
                task.id,
            ),
        )

        current_time = available_start
        schedule: list[ScheduledTask] = []
        unscheduled_minutes = 0
        bad_day_target_end = available_start + (available_end - available_start) * 0.6

        for task in ordered_tasks:
            if task.duration_minutes <= 0:
                continue

            scheduled_end = current_time + timedelta(minutes=task.duration_minutes)
            task_is_protected = self._is_deadline_protected(task, available_start)
            task_limit = available_end
            if bad_day and not task_is_protected:
                task_limit = min(available_end, bad_day_target_end)

            if scheduled_end > task_limit:
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

        return PlanningResult(
            schedule=schedule,
            is_overloaded=unscheduled_minutes > 0,
            unscheduled_minutes=unscheduled_minutes,
            bad_day=bad_day,
        )

    def _is_deadline_protected(self, task: Task, available_start: datetime) -> bool:
        return task.deadline <= available_start + self.due_soon_window

    @classmethod
    def energy_compatibility_rank(cls, task_energy_level: str, user_energy_level: str | None) -> int:
        """Return how closely a task's energy need matches the user's energy."""
        if user_energy_level is None:
            return 0

        task_rank = cls._energy_order.get(task_energy_level.lower(), 3)
        user_rank = cls._energy_order.get(user_energy_level.lower(), 3)
        return abs(task_rank - user_rank)
