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
    tasks_scheduled: int
    tasks_scheduled_completed: int
    plan_stability: dict[str, int]
    recovery_overview_missed: int
    recovery_overview_recovered: int
    deadline_behavior: dict[str, int]
    completion_rate: float
    estimated_completed_minutes: int
    actual_completed_minutes: int
    average_estimation_difference_minutes: float | None
    postponement_cycles: int
    most_productive_day: date | None
    daily_completed_tasks: dict[date, int]
    daily_scheduled_completed_tasks: dict[date, int]
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
        elif period == "year":
            week_start = week_start.replace(month=1, day=1)
            week_end = date(week_start.year, 12, 31)
            bucket_dates = [date(week_start.year, m, 1) for m in range(1, 13)]
        elif period == "all":
            if history_records:
                earliest_history = min(record.timestamp.date() for record in history_records)
                if earliest_history < week_start:
                    week_start = earliest_history
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
        scheduled_events = [record for record in week_history if record.event_type == "scheduled"]
        scheduled_task_anchors: dict[int, tuple[datetime, int]] = {}
        for record in scheduled_events:
            if (
                record.task_id not in scheduled_task_anchors
                or (record.timestamp, record.id) < scheduled_task_anchors[record.task_id]
            ):
                scheduled_task_anchors[record.task_id] = (record.timestamp, record.id)

        tasks_scheduled = len(scheduled_task_anchors)
        completed_events = [record for record in week_history if record.event_type == "completed"]

        scheduled_completed = 0
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
        daily_scheduled_completed_tasks = {bucket: 0 for bucket in bucket_dates}
        daily_planned_minutes = {bucket: 0 for bucket in bucket_dates}
        daily_estimated_minutes = {bucket: 0 for bucket in bucket_dates}
        daily_actual_minutes = {bucket: 0 for bucket in bucket_dates}
        def bucket_for(value: date) -> date:
            if period in ("all", "year"):
                return value.replace(day=1)
            return value

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

        for task_id, anchor in scheduled_task_anchors.items():
            post_anchor_completions = sorted(
                [
                    record
                    for record in completed_events
                    if record.task_id == task_id
                    and (record.timestamp, record.id) >= anchor
                ],
                key=lambda r: (r.timestamp, r.id),
            )
            if post_anchor_completions:
                scheduled_completed += 1
                completion_bucket = bucket_for(post_anchor_completions[0].timestamp.date())
                if completion_bucket in daily_scheduled_completed_tasks:
                    daily_scheduled_completed_tasks[completion_bucket] += 1

        most_productive_day = self._most_productive_day(daily_completed_tasks)

        history_by_task = defaultdict(list)
        for record in week_history:
            history_by_task[record.task_id].append(record)
        postponement_service = PostponementService()
        postponement_cycles = sum(
            postponement_service.analyze(task_id, records).postponement_count
            for task_id, records in history_by_task.items()
        )
        plan_stability = self._plan_stability(
            week_history,
            history_records,
            current_time,
        )
        recovery_overview_missed, recovery_overview_recovered = (
            self._recovery_overview(
                week_history,
                history_records,
                current_time,
            )
        )
        deadline_behavior = self._deadline_behavior(tasks, week_history)

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
            tasks_scheduled=tasks_scheduled,
            tasks_scheduled_completed=scheduled_completed,
            plan_stability=plan_stability,
            recovery_overview_missed=recovery_overview_missed,
            recovery_overview_recovered=recovery_overview_recovered,
            deadline_behavior=deadline_behavior,
            completion_rate=(scheduled_completed / tasks_scheduled
if tasks_scheduled
    else 0.0
),
            estimated_completed_minutes=estimated_completed_minutes,
            actual_completed_minutes=actual_completed_minutes,
            average_estimation_difference_minutes=average_estimation_difference_minutes,
            postponement_cycles=postponement_cycles,
            most_productive_day=most_productive_day,
            daily_completed_tasks=daily_completed_tasks,
            daily_scheduled_completed_tasks=daily_scheduled_completed_tasks,
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
    def _plan_stability(
        self,
        week_history: list[TaskHistory],
        history_records: list[TaskHistory],
        current_time: datetime,
    ) -> dict[str, int]:
        """Classify each task from its selected-period scheduled lifecycle."""

        scheduled_events_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        for record in week_history:
            if record.event_type == "scheduled":
                scheduled_events_by_task[record.task_id].append(record)

        history_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        for record in history_records:
            if record.timestamp <= current_time:
                history_by_task[record.task_id].append(record)

        stayed_as_planned = 0
        adjusted = 0
        missed = 0

        for task_id, scheduled_events in scheduled_events_by_task.items():
            anchor = min(scheduled_events, key=lambda record: (record.timestamp, record.id))
            records = sorted(
                (
                    record
                    for record in history_by_task[task_id]
                    if (record.timestamp, record.id) > (anchor.timestamp, anchor.id)
                ),
                key=lambda record: (record.timestamp, record.id),
            )

            had_missed = False
            had_adjustment = False
            completed = False

            for record in records:
                if record.event_type in {"rescheduled", "replanned", "recovered"}:
                    had_adjustment = True

                if record.event_type == "missed":
                    had_missed = True
                    had_adjustment = True
                    completed = False

                elif record.event_type == "recovered":
                    completed = False

                elif record.event_type == "completed":
                    completed = True

            if had_missed:
                missed += 1
            elif had_adjustment:
                adjusted += 1
            elif completed:
                stayed_as_planned += 1

        return {
            "stayed_as_planned": stayed_as_planned,
            "adjusted": adjusted,
            "missed": missed,
        }

    def _recovery_overview(
        self,
        week_history: list[TaskHistory],
        history_records: list[TaskHistory],
        current_time: datetime,
    ) -> tuple[int, int]:
        """Count recovery only within the Plan Stability missed cohort."""

        scheduled_events_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        for record in week_history:
            if record.event_type == "scheduled":
                scheduled_events_by_task[record.task_id].append(record)

        history_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        for record in history_records:
            if record.timestamp <= current_time:
                history_by_task[record.task_id].append(record)

        missed_tasks = 0
        recovered_tasks = 0

        for task_id, scheduled_events in scheduled_events_by_task.items():
            anchor = min(scheduled_events, key=lambda record: (record.timestamp, record.id))
            missed = False
            recovered = False

            records = sorted(
                (
                    record
                    for record in history_by_task[task_id]
                    if (record.timestamp, record.id) > (anchor.timestamp, anchor.id)
                ),
                key=lambda record: (record.timestamp, record.id),
            )
            for record in records:
                if record.event_type == "missed":
                    missed = True
                elif missed and record.event_type in {"recovered", "replanned"}:
                    recovered = True

            if missed:
                missed_tasks += 1
                if recovered:
                    recovered_tasks += 1

        return missed_tasks, recovered_tasks

    def _deadline_behavior(
        self,
        tasks: list[Task],
        week_history: list[TaskHistory],
    ) -> dict[str, int]:
        """Classify deadline-bearing task outcomes for tasks scheduled in the selected period."""

        task_by_id = {task.id: task for task in tasks}

        scheduled_events_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        events_by_task: dict[int, list[TaskHistory]] = defaultdict(list)
        for record in week_history:
            events_by_task[record.task_id].append(record)
            if record.event_type == "scheduled":
                scheduled_events_by_task[record.task_id].append(record)

        completed_before_deadline = 0
        rescheduled = 0
        missed_deadline = 0

        for task_id, scheduled_events in scheduled_events_by_task.items():
            task = task_by_id.get(task_id)

            if task is None or task.deadline is None:
                continue

            anchor = min(scheduled_events, key=lambda record: (record.timestamp, record.id))
            records = [
                record
                for record in events_by_task[task_id]
                if (record.timestamp, record.id) >= (anchor.timestamp, anchor.id)
            ]

            outcome_events = [
                record
                for record in records
                if record.event_type in {"completed", "missed"}
            ]

            if not outcome_events:
                continue

            outcome = max(
                outcome_events,
                key=lambda record: (record.timestamp, record.id),
            )

            if (
                outcome.event_type == "completed"
                and outcome.timestamp > task.deadline
            ):
                missed_deadline += 1
                continue

            if (
                outcome.event_type == "missed"
                and outcome.timestamp >= task.deadline
            ):
                missed_deadline += 1
                continue

            had_valid_reschedule = any(
                record.event_type == "rescheduled"
                and record.timestamp < task.deadline
                for record in records
            )

            if had_valid_reschedule:
                rescheduled += 1
            elif (
                outcome.event_type == "completed"
                and outcome.timestamp <= task.deadline
            ):
                completed_before_deadline += 1

        return {
            "completed_before_deadline": completed_before_deadline,
            "rescheduled": rescheduled,
            "missed_deadline": missed_deadline,
        }

    def _most_productive_day(
        self,
        daily_completed_tasks: dict[date, int],
    ) -> date | None:
        highest_count = max(daily_completed_tasks.values())
        if highest_count == 0:
            return None

        return min(
            day
            for day, count in daily_completed_tasks.items()
            if count == highest_count
        )


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
