from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.planning import PlanRequest, PlanResponse, ScheduledTaskResponse
from app.services.history_state import recovery_state_by_task_id
from app.services.planning import PlanningEngine

router = APIRouter(tags=["planning"])


def has_complete_schedule(task: Task) -> bool:
    return task.scheduled_start is not None and task.scheduled_end is not None


def user_wall_clock(value: datetime, timezone_name: str | None) -> datetime:
    """Express a request timestamp as a naive wall-clock value in the user's frame.

    Persisted schedules are stored as naive datetimes and the browser
    displays those naive values as the user's local time, so every planning
    comparison must use that same frame. An aware request instant is
    converted with the browser-supplied IANA timezone; naive values and
    missing/invalid timezones keep the previous server-local behavior.
    """
    if value.tzinfo is None or not timezone_name:
        return PlanningEngine._to_naive_local(value)
    try:
        return value.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, ValueError):
        return PlanningEngine._to_naive_local(value)


def persisted_schedule(
    tasks: list[Task],
    planning_reference_time: datetime,
    bad_day: bool = False,
    user_energy_level: str | None = None,
) -> list[ScheduledTaskResponse]:
    """Return an already-created plan without moving it as wall-clock time moves.

    The per-task reason is reconstructed with the same deterministic rule
    the planner uses, from already-persisted task fields and this request's
    planning context. This performs no planning run: the schedule, history,
    and refresh flags are untouched, so idempotency is unchanged.
    """
    engine = PlanningEngine()
    if bad_day:
        user_energy_level = "low"
    # Reuse the planner's own anchor so date-based explanations match the
    # strings the original planning run produced for these same slots.
    reason_anchor = planning_start_with_persisted_schedule(
        tasks, planning_reference_time
    )
    responses = []
    for task in sorted(tasks, key=lambda task: (task.scheduled_start, task.id)):
        persisted_end = PlanningEngine._to_naive_local(task.scheduled_end)
        responses.append(
            ScheduledTaskResponse(
                task_id=task.id,
                title=task.title,
                scheduled_start=task.scheduled_start,
                scheduled_end=task.scheduled_end,
                reason=engine._compute_reason(
                    task,
                    reason_anchor,
                    bad_day,
                    PlanningEngine._is_deadline_protected(task, reason_anchor),
                    persisted_end,
                    persisted_end,
                    user_energy_level,
                ),
            )
        )
    return responses


def planning_start_with_persisted_schedule(
    tasks: list[Task], requested_start: datetime
) -> datetime:
    """Anchor refreshes to a still-active persisted plan, when one exists."""
    requested_start = PlanningEngine._to_naive_local(requested_start)

    persisted_starts = [
        PlanningEngine._to_naive_local(task.scheduled_start)
        for task in tasks
        if (
            not task.completed
            and has_complete_schedule(task)
            # A slot ending at or before the requested planning reference is
            # stale. It must not pull a refresh back into the past.
            and PlanningEngine._to_naive_local(task.scheduled_end) > requested_start
        )
    ]

    if not persisted_starts:
        return requested_start

    earliest_persisted_start = min(persisted_starts)

    return min(requested_start, earliest_persisted_start)


def schedule_change_reason(tasks: list[Task]) -> str:
    refresh_reasons = {
        task.schedule_refresh_reason
        for task in tasks
        if task.schedule_needs_refresh
    }
    if "added" in refresh_reasons:
        return "Schedule changed after adding a task"
    if "edited" in refresh_reasons:
        return "Schedule changed after editing a task"
    return "Plan reshaped"


def bad_day_history_reason(
    task: Task,
    planning_reference_time: datetime,
    event_type: str,
) -> str:
    """Describe the concrete Bad Day policy that affected this task."""
    deadline = PlanningEngine._to_naive_local(task.deadline)
    if deadline < planning_reference_time:
        return "Kept because the deadline has passed."
    if deadline.date() == planning_reference_time.date():
        return "Kept because the deadline is today."
    if deadline.date() == (planning_reference_time + timedelta(days=1)).date():
        return "Kept because the deadline is tomorrow."
    if task.energy_level == "low":
        return "Prioritized because it matches your current energy."
    if event_type == "scheduled":
        return "Scheduled within your reduced workload."
    return "Moved to reduce today's workload."


def expired_persisted_tasks(
    tasks: list[Task],
    planning_reference_time: datetime,
) -> list[Task]:
    """Return scheduled, incomplete tasks whose slot has fully elapsed.

    Unlike stale_persisted_tasks, this ignores the missed-recovery state on
    purpose: a persisted slot with scheduled_end <= now is stale regardless
    of history and must never be returned as the current schedule.
    """
    return [
        task
        for task in tasks
        if (
            not task.completed
            and has_complete_schedule(task)
            and PlanningEngine._to_naive_local(task.scheduled_end)
            <= planning_reference_time
        )
    ]


def stale_persisted_tasks(
    tasks: list[Task],
    planning_reference_time: datetime,
    outstanding_missed_ids: set[int],
) -> list[Task]:
    """Return scheduled, incomplete tasks whose opportunity has elapsed.

    A deadline alone does not start a missed cycle. A task enters that
    lifecycle only after its persisted scheduled opportunity has ended.
    """
    return [
        task
        for task in tasks
        if (
            not task.completed
            and task.id not in outstanding_missed_ids
            and has_complete_schedule(task)
            and PlanningEngine._to_naive_local(task.scheduled_end)
            <= planning_reference_time
        )
    ]
def overdue_tasks(
    tasks: list[Task],
    planning_reference_time: datetime,
) -> list[Task]:
    """Return incomplete tasks whose deadline has passed."""
    return [
        task
        for task in tasks
        if (
            not task.completed
            and task.deadline is not None
            and PlanningEngine._to_naive_local(task.deadline)
            <= planning_reference_time
        )
    ]

@router.post("/plan", response_model=PlanResponse)
def create_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    incomplete_tasks = [task for task in tasks if not task.completed]
    refresh_reason = schedule_change_reason(incomplete_tasks)
    planning_reference_time = user_wall_clock(
        plan_request.available_start, plan_request.timezone
    )
    planning_end_time = user_wall_clock(
        plan_request.available_end, plan_request.timezone
    )
    plan_reshaped_at = datetime.now()
    _, outstanding_missed_ids = recovery_state_by_task_id(
        db, [task.id for task in incomplete_tasks]
    )
    previously_scheduled_ids = {
        task_id
        for (task_id,) in (
            db.query(TaskHistory.task_id)
            .filter(
                TaskHistory.task_id.in_([task.id for task in incomplete_tasks]),
                TaskHistory.event_type == "scheduled",
            )
            .all()
        )
    }
    newly_missed_ids: set[int] = set()

    # A fully elapsed persisted slot is a missed scheduled opportunity, not
    # an ordinary schedule change. Open the established missed cycle before
    # planning so an included task is recovered below instead of rescheduled.
    for task in stale_persisted_tasks(
        incomplete_tasks, planning_reference_time, outstanding_missed_ids
    ):
        old_start = task.scheduled_start
        old_end = task.scheduled_end
        db.add(
            TaskHistory(
                task_id=task.id,
                user_id=current_user.id,
                event_type="missed",
                task_title=task.title,
                timestamp=plan_reshaped_at,
                scheduled_start=old_start,
                scheduled_end=old_end,
                old_start=old_start,
                old_end=old_end,
                reason="Scheduled opportunity passed",
            )
        )
        task.status = "missed"
        task.scheduled_start = None
        task.scheduled_end = None
        task.schedule_needs_refresh = True
        newly_missed_ids.add(task.id)
    outstanding_missed_ids |= newly_missed_ids

    # A fully elapsed slot that was skipped above is already inside an open
    # missed cycle, so recording another "missed" event would corrupt the
    # recovery lifecycle. Its missed opportunity is already represented in
    # outstanding_missed_ids. Still, the expired slot itself must not survive:
    # clear it and force a refresh so the idempotent early return below can
    # never serve it as the current schedule.
    for task in expired_persisted_tasks(incomplete_tasks, planning_reference_time):
        if has_complete_schedule(task):
            task.scheduled_start = None
            task.scheduled_end = None
            task.schedule_needs_refresh = True

    newly_overdue_ids: set[int] = set()

    for task in overdue_tasks(incomplete_tasks, planning_reference_time):
        existing_overdue = (
            db.query(TaskHistory.id)
            .filter(
                TaskHistory.task_id == task.id,
                TaskHistory.event_type == "overdue",
            )
            .first()
        )

        if existing_overdue is None:
            db.add(
                TaskHistory(
                    task_id=task.id,
                    user_id=current_user.id,
                    event_type="overdue",
                    task_title=task.title,
                    timestamp=plan_reshaped_at,
                    reason="Task deadline passed",
                )
            )
            newly_overdue_ids.add(task.id)

    # A deadline never creates a missed event, but it does close an already
    # open recovery opportunity. Keep that task missed and unscheduled rather
    # than creating another future slot after its final deadline has passed.

    # An unchanged plan is already the user's deliberate plan for the day.
    # This includes tasks intentionally left unscheduled because the day is
    # overloaded. Reusing it prevents the current clock from shifting the
    # scheduled subset on a repeated Plan My Day call.
    if (
        incomplete_tasks
        and not plan_request.force_replan
        and not any(task.schedule_needs_refresh for task in incomplete_tasks)
    ):
        unscheduled_minutes = sum(
            task.duration_minutes
            for task in incomplete_tasks
            if not has_complete_schedule(task)
        )
        return PlanResponse(
            schedule=persisted_schedule(
                [task for task in incomplete_tasks if has_complete_schedule(task)],
                planning_reference_time,
                plan_request.bad_day,
                plan_request.energy_level,
            ),
            is_overloaded=unscheduled_minutes > 0,
            unscheduled_minutes=unscheduled_minutes,
            bad_day=plan_request.bad_day,
            bad_day_protected_count=0,
            bad_day_capacity_minutes=0,
            schedule_refresh_reason=schedule_change_reason(incomplete_tasks),
        )

    planning_anchor = planning_start_with_persisted_schedule(
        tasks,
        planning_reference_time,
    )

    if outstanding_missed_ids:
        planning_anchor = max(planning_anchor, planning_reference_time)

    result = PlanningEngine().generate_schedule(
        tasks,
        planning_anchor,
        planning_end_time,
        plan_request.energy_level,
        plan_request.bad_day,
        preserve_persisted_slots=not plan_request.force_replan,
    )

    scheduled_task_ids = {item.task_id for item in result.schedule}
    for item in result.schedule:
        task = (
            db.query(Task)
            .filter(Task.id == item.task_id, Task.user_id == current_user.id)
            .first()
        )
        if task is not None:
            old_start = task.scheduled_start
            old_end = task.scheduled_end
            schedule_changed = (
                old_start != item.scheduled_start
                or old_end != item.scheduled_end
            )
            task.scheduled_start = item.scheduled_start
            task.scheduled_end = item.scheduled_end
            task.schedule_needs_refresh = False
            task.schedule_refresh_reason = None
            was_recovered = False

            if task.id in outstanding_missed_ids:
                # A recovery is meaningful only once Plan My Day actually
                # contains the missed task. The outstanding missed-cycle state
                # is authoritative even if a prior request normalized status.
                # It also prevents this task from receiving a Rescheduled
                # event in the same persistence operation.
                task.status = "pending"
                was_recovered = True

                db.add(
                    TaskHistory(
                        task_id=task.id,
                        user_id=current_user.id,
                        event_type="recovered",
                        task_title=task.title,
                        timestamp=plan_reshaped_at,
                        old_start=old_start,
                        old_end=old_end,
                        new_start=item.scheduled_start,
                        new_end=item.scheduled_end,
                        reason="Missed task was included in Plan My Day",
                    )
                )

            # Record a schedule change only when the task already had a
            # schedule and its new schedule is actually different.
            # A newly scheduled task gets "scheduled", while a recovered
            # task gets "recovered" only.
            both_slots_are_past = (
                old_end is not None
                and PlanningEngine._to_naive_local(old_end)
                <= planning_reference_time
                and PlanningEngine._to_naive_local(item.scheduled_end)
                <= planning_reference_time
            )
            if schedule_changed and not was_recovered and not both_slots_are_past:
                if old_start is not None and old_end is not None:
                    db.add(
                        TaskHistory(
                            task_id=task.id,
                            user_id=current_user.id,
                            event_type="rescheduled",
                            task_title=task.title,
                            timestamp=plan_reshaped_at,
                            scheduled_start=item.scheduled_start,
                            scheduled_end=item.scheduled_end,
                            old_start=old_start,
                            old_end=old_end,
                            new_start=item.scheduled_start,
                            new_end=item.scheduled_end,
                            reason=(
                                bad_day_history_reason(
                                    task,
                                    planning_reference_time,
                                    "rescheduled",
                                )
                                if plan_request.bad_day
                                else refresh_reason
                            ),
                        )
                    )
                elif task.id not in previously_scheduled_ids:
                    db.add(
                        TaskHistory(
                            task_id=task.id,
                            user_id=current_user.id,
                            event_type="scheduled",
                            task_title=task.title,
                            timestamp=plan_reshaped_at,
                            scheduled_start=item.scheduled_start,
                            scheduled_end=item.scheduled_end,
                            old_start=old_start,
                            old_end=old_end,
                            new_start=item.scheduled_start,
                            new_end=item.scheduled_end,
                            reason=(
                                bad_day_history_reason(
                                    task,
                                    planning_reference_time,
                                    "scheduled",
                                )
                                if plan_request.bad_day
                                else "Added to your plan"
                            ),
                        )
                    )
    for task in tasks:
        if not task.completed and task.id not in scheduled_task_ids:
            task.scheduled_start = None
            task.scheduled_end = None
            task.schedule_needs_refresh = False
            task.schedule_refresh_reason = None
    db.commit()

    refresh_reason = schedule_change_reason(incomplete_tasks)
    task_map = {task.id: task for task in incomplete_tasks}
    protected_count = 0
    for item in result.schedule:
        task = task_map.get(item.task_id)
        if task is not None and PlanningEngine._is_deadline_protected(task, planning_reference_time):
            protected_count += 1
    bad_day_capacity = (
        int(
            (plan_request.available_end - plan_request.available_start).total_seconds()
            / 60
            * PlanningEngine.bad_day_capacity_ratio
        )
        if plan_request.bad_day
        else 0
    )

    return PlanResponse(
        schedule=[
            ScheduledTaskResponse(
                task_id=item.task_id,
                title=item.title,
                scheduled_start=item.scheduled_start,
                scheduled_end=item.scheduled_end,
                reason=item.reason,
            )
            for item in result.schedule
        ],
        is_overloaded=result.is_overloaded,
        unscheduled_minutes=result.unscheduled_minutes,
        bad_day=result.bad_day,
        bad_day_protected_count=protected_count,
        bad_day_capacity_minutes=bad_day_capacity,
        schedule_refresh_reason=refresh_reason,
    )
