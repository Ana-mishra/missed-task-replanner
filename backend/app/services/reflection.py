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
    tasks_recovered: int
    completion_rate: float
    estimated_completed_minutes: int
    actual_completed_minutes: int
    average_estimation_difference_minutes: float | None
    postponement_cycles: int
    most_productive_day: date | None
    daily_completed_tasks: dict[date, int]
    daily_planned_minutes: dict[date, int]
    daily_estimated_minutes: dict[date, int]
    daily_actual_minutes: dict[date, int]
    progress_level: int
    progress_percent: float
    previous_tasks_completed: int | None = None
    previous_completion_rate: float | None = None
    previous_tasks_missed: int | None = None
    previous_tasks_recovered: int | None = None


class ReflectionService:
    """Builds an objective weekly summary from task history."""

    def calculate(
        self,
        tasks: list[Task],
        history_records: list[TaskHistory],
        week_start: date,
        current_time: datetime,
        period: str = "week",
    ) -> WeeklyReflectionResult:
        if period == "month":
            next_month = (week_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            week_end = next_month - timedelta(days=1)
            bucket_dates = [week_start + timedelta(days=offset) for offset in range((week_end - week_start).days + 1)]
        elif period == "all":
            week_start = week_start.replace(day=1)
            week_end = current_time.date()
            bucket_dates = []
            bucket = week_start
            while bucket <= week_end:
                bucket_dates.append(bucket)
                next_bucket = (bucket.replace(day=28) + timedelta(days=4)).replace(day=1)
                bucket = next_bucket
        else:
            week_end = week_start + timedelta(days=6)
            bucket_dates = [week_start + timedelta(days=offset) for offset in range(7)]
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

        daily_completed_tasks = {bucket: 0 for bucket in bucket_dates}
        daily_planned_minutes = {bucket: 0 for bucket in bucket_dates}
        daily_estimated_minutes = {bucket: 0 for bucket in bucket_dates}
        daily_actual_minutes = {bucket: 0 for bucket in bucket_dates}
        def bucket_for(value: date) -> date:
            return value.replace(day=1) if period == "all" else value

        period_end_exclusive = datetime.combine(week_end + timedelta(days=1), datetime.min.time())
        for task in tasks:
            if (
                task.scheduled_start is not None
                and task.scheduled_end is not None
                and week_start_datetime <= task.scheduled_start < period_end_exclusive
            ):
                daily_planned_minutes[bucket_for(task.scheduled_start.date())] += max(
                    0,
                    int((task.scheduled_end - task.scheduled_start).total_seconds() // 60),
                )
        for record in completed_events:
            bucket = bucket_for(record.timestamp.date())
            daily_completed_tasks[bucket] += 1
            task = task_by_id.get(record.task_id)
            if task is not None:
                daily_estimated_minutes[bucket] += task.duration_minutes
                daily_actual_minutes[bucket] += task.actual_duration_minutes or 0
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
            current_time,
        )
        completed_and_missed = event_counts["completed"] + event_counts["missed"]

        previous_tasks_completed = None
        previous_completion_rate = None
        previous_tasks_missed = None
        previous_tasks_recovered = None
        if period != "all":
            period_days = (week_end - week_start).days + 1
            previous_end = week_start - timedelta(days=1)
            previous_start = previous_end - timedelta(days=period_days - 1)
            previous_history = [
                record
                for record in history_records
                if previous_start <= record.timestamp.date() <= previous_end
                and record.timestamp <= current_time
            ]
            previous_counts = Counter(record.event_type for record in previous_history)
            previous_tasks_completed = previous_counts["completed"]
            previous_tasks_missed = previous_counts["missed"]
            previous_tasks_recovered = previous_counts["recovered"]
            previous_total = previous_tasks_completed + previous_tasks_missed
            previous_completion_rate = previous_tasks_completed / previous_total if previous_total else 0.0

        return WeeklyReflectionResult(
            week_start=week_start,
            week_end=week_end,
            tasks_created=event_counts["created"],
            tasks_completed=event_counts["completed"],
            tasks_missed=event_counts["missed"],
            tasks_replanned=event_counts["replanned"],
            tasks_recovered=event_counts["recovered"],
            completion_rate=(event_counts["completed"] / completed_and_missed if completed_and_missed else 0.0),
            estimated_completed_minutes=estimated_completed_minutes,
            actual_completed_minutes=actual_completed_minutes,
            average_estimation_difference_minutes=average_estimation_difference_minutes,
            postponement_cycles=postponement_cycles,
            most_productive_day=most_productive_day,
            daily_completed_tasks=daily_completed_tasks,
            daily_planned_minutes=daily_planned_minutes,
            daily_estimated_minutes=daily_estimated_minutes,
            daily_actual_minutes=daily_actual_minutes,
            progress_level=progress.progress_level,
            progress_percent=progress.progress_percent,
            previous_tasks_completed=previous_tasks_completed,
            previous_completion_rate=previous_completion_rate,
            previous_tasks_missed=previous_tasks_missed,
            previous_tasks_recovered=previous_tasks_recovered,
        )

    def _most_productive_day(self, daily_completed_tasks: dict[date, int]) -> date | None:
        highest_count = max(daily_completed_tasks.values())
        if highest_count == 0:
            return None
        return min(day for day, count in daily_completed_tasks.items() if count == highest_count)

    def daily_glance(
        self,
        tasks: list[Task],
        history_records: list[TaskHistory],
        selected_date: date,
    ) -> dict[str, int | None]:
        """Return task/history facts for one reflection date."""
        events = [record for record in history_records if record.timestamp.date() == selected_date]
        planned_work_minutes = sum(
            max(0, int((task.scheduled_end - task.scheduled_start).total_seconds() // 60))
            for task in tasks
            if task.scheduled_start is not None
            and task.scheduled_end is not None
            and task.scheduled_start.date() == selected_date
        )
        return {
            "completed": sum(record.event_type == "completed" for record in events),
            "missed": sum(record.event_type == "missed" for record in events),
            "recovered": sum(record.event_type == "recovered" for record in events),
            "planned_work_minutes": planned_work_minutes,
            "available_minutes": None,
        }

    def reflection_streak(
        self, reflection_dates: list[date], selected_date: date
    ) -> tuple[int, list[dict[str, object]]]:
        reflected_dates = set(reflection_dates)
        streak_days = 0
        cursor = selected_date
        while cursor in reflected_dates:
            streak_days += 1
            cursor -= timedelta(days=1)
        recent_days = [
            {"date": selected_date - timedelta(days=offset), "reflected": selected_date - timedelta(days=offset) in reflected_dates}
            for offset in range(4, -1, -1)
        ]
        return streak_days, recent_days
