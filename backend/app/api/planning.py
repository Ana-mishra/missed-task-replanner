from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.planning import PlanRequest, PlanResponse, ScheduledTaskResponse
from app.services.planning import PlanningEngine

router = APIRouter(tags=["planning"])


def has_complete_schedule(task: Task) -> bool:
    return task.scheduled_start is not None and task.scheduled_end is not None


def persisted_schedule(tasks: list[Task]) -> list[ScheduledTaskResponse]:
    """Return an already-created plan without moving it as wall-clock time moves."""
    return [
        ScheduledTaskResponse(
            task_id=task.id,
            title=task.title,
            scheduled_start=task.scheduled_start,
            scheduled_end=task.scheduled_end,
        )
        for task in sorted(tasks, key=lambda task: (task.scheduled_start, task.id))
    ]


@router.post("/plan", response_model=PlanResponse)
def create_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    incomplete_tasks = [task for task in tasks if not task.completed]

    # An unchanged plan is already the user's deliberate plan for the day.
    # This includes tasks intentionally left unscheduled because the day is
    # overloaded. Reusing it prevents the current clock from shifting the
    # scheduled subset on a repeated Plan My Day call.
    if incomplete_tasks and not any(task.schedule_needs_refresh for task in incomplete_tasks):
        unscheduled_minutes = sum(
            task.duration_minutes
            for task in incomplete_tasks
            if not has_complete_schedule(task)
        )
        return PlanResponse(
            schedule=persisted_schedule(
                [task for task in incomplete_tasks if has_complete_schedule(task)]
            ),
            is_overloaded=unscheduled_minutes > 0,
            unscheduled_minutes=unscheduled_minutes,
            bad_day=plan_request.bad_day,
        )

    result = PlanningEngine().generate_schedule(
        tasks,
        plan_request.available_start,
        plan_request.available_end,
        plan_request.energy_level,
        plan_request.bad_day,
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
            if schedule_changed:
                was_previously_scheduled = old_start is not None and old_end is not None
                db.add(
                    TaskHistory(
                        task_id=task.id,
                        user_id=current_user.id,
                        event_type="rescheduled" if was_previously_scheduled else "scheduled",
                        scheduled_start=item.scheduled_start,
                        scheduled_end=item.scheduled_end,
                        old_start=old_start,
                        old_end=old_end,
                        new_start=item.scheduled_start,
                        new_end=item.scheduled_end,
                        reason=(
                            "Schedule updated by planning"
                            if was_previously_scheduled
                            else "Task added to the schedule"
                        ),
                    )
                )
    for task in tasks:
        if not task.completed and task.id not in scheduled_task_ids:
            task.scheduled_start = None
            task.scheduled_end = None
            task.schedule_needs_refresh = False
    db.commit()

    return PlanResponse(
        schedule=[
            ScheduledTaskResponse(
                task_id=item.task_id,
                title=item.title,
                scheduled_start=item.scheduled_start,
                scheduled_end=item.scheduled_end,
            )
            for item in result.schedule
        ],
        is_overloaded=result.is_overloaded,
        unscheduled_minutes=result.unscheduled_minutes,
        bad_day=result.bad_day,
    )
