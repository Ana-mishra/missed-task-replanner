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
    bad_day_capacity_ratio = 0.6

    @staticmethod
    def _to_naive_local(value: datetime) -> datetime:
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value

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
        preserve_persisted_slots: bool = False,
    ) -> PlanningResult:
        """Schedule unfinished tasks in deadline and priority order.

        A task is overdue when its deadline is before the available start time.
        Tasks that do not fit are skipped, allowing later shorter tasks to use
        any remaining time.
        """
        if available_start.tzinfo is not None:
            available_start = available_start.astimezone().replace(tzinfo=None)

        if available_end.tzinfo is not None:
            available_end = available_end.astimezone().replace(tzinfo=None)

        if available_end < available_start:
            raise ValueError("available_end must be after available_start")

        unfinished_tasks = [task for task in tasks if not task.completed]
        # Bad Day Mode is intentionally a two-layer policy. Deadline safety
        # is a hard ordering layer; energy fit ranks only work that is safe to
        # move. This prevents a pleasant low-energy task from displacing work
        # due tomorrow.
        if bad_day:
            user_energy_level = "low"
            ordered_tasks = sorted(
                unfinished_tasks,
                key=lambda task: self._bad_day_sort_key(task, available_start),
            )
        else:
            # Preserve the established normal-day ordering exactly.
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
        bad_day_target_end = available_start + (
            available_end - available_start
        ) * self.bad_day_capacity_ratio

        for task in ordered_tasks:
            if task.duration_minutes <= 0:
                continue

            task_is_protected = self._is_deadline_protected(task, available_start)
            task_limit = available_end
            if bad_day and not task_is_protected:
                task_limit = min(available_end, bad_day_target_end)

            persisted_start = (
                self._to_naive_local(task.scheduled_start)
                if task.scheduled_start is not None
                else None
            )
            persisted_end = (
                self._to_naive_local(task.scheduled_end)
                if task.scheduled_end is not None
                else None
            )
            persisted_duration_matches = (
                persisted_start is not None
                and persisted_end is not None
                and persisted_end - persisted_start
                == timedelta(minutes=task.duration_minutes)
            )
            can_keep_persisted_slot = (
                preserve_persisted_slots
                and task.schedule_refresh_reason != "edited"
                and persisted_duration_matches
                and (
                    persisted_start >= current_time
                    or (not schedule and persisted_end > current_time)
                )
                # A fully elapsed slot is stale even if an upstream caller
                # supplied an older anchor. Partially elapsed first slots keep
                # the existing product behavior while they are still active.
                and persisted_end > available_start
                and persisted_end <= task_limit
            )

            if can_keep_persisted_slot:
                schedule.append(
                    ScheduledTask(
                        task_id=task.id,
                        title=task.title,
                        scheduled_start=persisted_start,
                        scheduled_end=persisted_end,
                    )
                )
                current_time = persisted_end
                continue

            scheduled_end = current_time + timedelta(minutes=task.duration_minutes)

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
        deadline = self._to_naive_local(task.deadline)
        # Calendar-day protection reflects what a user means by "due
        # tomorrow" even when their available window starts late in the day.
        return deadline.date() <= (available_start + timedelta(days=1)).date()

    def _bad_day_sort_key(self, task: Task, available_start: datetime) -> tuple:
        """Order protected work before low-energy movable work.

        Priority breaks ties only after two movable tasks have comparable
        energy fit, preserving a deterministic and explainable policy.
        """
        protected = self._is_deadline_protected(task, available_start)
        if protected:
            return (
                0,
                task.deadline >= available_start,
                task.deadline,
                self.priority_rank(task.priority),
                task.duration_minutes,
                task.id,
            )
        return (
            1,
            self.energy_compatibility_rank(task.energy_level, "low"),
            task.deadline,
            self.priority_rank(task.priority),
            task.duration_minutes,
            task.id,
        )

    @classmethod
    def energy_compatibility_rank(cls, task_energy_level: str, user_energy_level: str | None) -> int:
        """Return how closely a task's energy need matches the user's energy."""
        if user_energy_level is None:
            return 0

        task_rank = cls._energy_order.get(task_energy_level.lower(), 3)
        user_rank = cls._energy_order.get(user_energy_level.lower(), 3)
        return abs(task_rank - user_rank)
