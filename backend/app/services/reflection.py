from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.models.task import Task
from app.models.task_history import TaskHistory
from app.services.postponement import PostponementService
from app.services.progress import ProgressService


@dataclass(frozen=True)
class WeeklyReflectionResult:
    week_start: date
    week_end: date
    tasks_created: int
    tasks_completed: int
    tasks_missed: int
    tasks_replanned: int
    completion_rate: float
    estimated_completed_minutes: int
    actual_completed_minutes: int
    average_estimation_difference_minutes: float | None
    postponement_cycles: int
    most_productive_day: date | None
    daily_completed_tasks: dict[date, int]
    progress_level: int
    progress_percent: float


class ReflectionService:
    """Builds an objective weekly summary from task history."""

    def calculate(
        self,
        tasks: list[Task],
        history_records: list[TaskHistory],
        week_start: date,
        current_time: datetime,
    ) -> WeeklyReflectionResult:
        week_end = week_start + timedelta(days=6)
        week_end_exclusive = datetime.combine(week_end + timedelta(days=1), datetime.min.time())
        week_start_datetime = datetime.combine(week_start, datetime.min.time())
        week_history = [
            record
            for record in history_records
            if week_start_datetime <= record.timestamp < week_end_exclusive
            and record.timestamp <= current_time
        ]
        event_counts = Counter(record.event_type for record in week_history)
        completed_events = [record for record in week_history if record.event_type == "completed"]
        task_by_id = {task.id: task for task in tasks}
        completed_event_tasks = [
            task_by_id[record.task_id]
            for record in completed_events
            if record.task_id in task_by_id
        ]

        estimated_completed_minutes = sum(task.duration_minutes for task in completed_event_tasks)
        actual_completed_minutes = sum(
            task.actual_duration_minutes
            for task in completed_event_tasks
            if task.actual_duration_minutes is not None
        )
        estimation_differences = [
            task.actual_duration_minutes - task.duration_minutes
            for task in completed_event_tasks
            if task.actual_duration_minutes is not None
        ]
        average_estimation_difference_minutes = (
            sum(estimation_differences) / len(estimation_differences)
            if estimation_differences
            else None
        )

        daily_completed_tasks = {week_start + timedelta(days=offset): 0 for offset in range(7)}
        for record in completed_events:
            daily_completed_tasks[record.timestamp.date()] += 1
        most_productive_day = self._most_productive_day(daily_completed_tasks)

        history_by_task = defaultdict(list)
        for record in week_history:
            history_by_task[record.task_id].append(record)
        postponement_service = PostponementService()
        postponement_cycles = sum(
            postponement_service.analyze(task_id, records).postponement_count
            for task_id, records in history_by_task.items()
        )

        progress = ProgressService().calculate(
            tasks,
            [record for record in history_records if record.event_type == "completed"],
            current_time.date(),
        )
        completed_and_missed = event_counts["completed"] + event_counts["missed"]

        return WeeklyReflectionResult(
            week_start=week_start,
            week_end=week_end,
            tasks_created=event_counts["created"],
            tasks_completed=event_counts["completed"],
            tasks_missed=event_counts["missed"],
            tasks_replanned=event_counts["replanned"],
            completion_rate=(event_counts["completed"] / completed_and_missed if completed_and_missed else 0.0),
            estimated_completed_minutes=estimated_completed_minutes,
            actual_completed_minutes=actual_completed_minutes,
            average_estimation_difference_minutes=average_estimation_difference_minutes,
            postponement_cycles=postponement_cycles,
            most_productive_day=most_productive_day,
            daily_completed_tasks=daily_completed_tasks,
            progress_level=progress.progress_level,
            progress_percent=progress.progress_percent,
        )

    def _most_productive_day(self, daily_completed_tasks: dict[date, int]) -> date | None:
        highest_count = max(daily_completed_tasks.values())
        if highest_count == 0:
            return None
        return min(day for day, count in daily_completed_tasks.items() if count == highest_count)
