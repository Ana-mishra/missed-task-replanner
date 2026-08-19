from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.planning import PlanRequest, ScheduledTaskResponse
from app.schemas.replanning import ReplanResponse
from app.services.history_state import recovery_state_by_task_id
from app.services.replanning import ReplanningEngine

router = APIRouter(tags=["replanning"])


@router.post("/replan/{task_id}", response_model=ReplanResponse)
def replan_task(
    task_id: int,
    replan_request: PlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    missed_task = (
        db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    )
    if missed_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if missed_task.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed tasks cannot be replanned",
        )

    replanning_engine = ReplanningEngine()
    missed_start = missed_task.scheduled_start
    missed_end = missed_task.scheduled_end
    recovered_ids, outstanding_missed_ids = recovery_state_by_task_id(db, [task_id])
    # A pending task may start its first missed cycle. Later calls only start a
    # new cycle after the recovered slot has actually passed, preventing a
    # repeated button click from manufacturing another recovery event.
    current_window_start = replanning_engine._to_naive_local(replan_request.available_start)
    prior_slot_has_passed = (
        missed_end is not None
        and replanning_engine._to_naive_local(missed_end) <= current_window_start
    )
    starts_new_miss = (
        task_id in outstanding_missed_ids
        or missed_task.status == "missed"
        or task_id not in recovered_ids
        or prior_slot_has_passed
    )
    recovery_open = task_id in outstanding_missed_ids
    if starts_new_miss and not recovery_open:
        db.add(
            TaskHistory(
                task_id=missed_task.id,
                user_id=current_user.id,
                event_type="missed",
                scheduled_start=missed_task.scheduled_start,
                scheduled_end=missed_task.scheduled_end,
                old_start=missed_start,
                old_end=missed_end,
                reason="Task was not completed",
            )
        )
        recovery_open = True
    if recovery_open:
        missed_task.status = "missed"
        missed_task.completed = False
    incomplete_tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id, Task.completed.is_(False))
        .all()
    )
    result = replanning_engine.generate_revised_schedule(
        incomplete_tasks,
        missed_task,
        replan_request.available_start,
        replan_request.available_end,
    )

    scheduled_by_id = {item.task_id: item for item in result.schedule}
    missed_task_was_scheduled = missed_task.id in scheduled_by_id
    if recovery_open and missed_task_was_scheduled:
        # A successful replan puts the task back in the active task list.
        missed_task.status = "pending"
    current_day = replanning_engine._to_naive_local(
        replan_request.available_start
    ).date()

    affected_task_ids = {
        task.id
        for task in incomplete_tasks
        if task.id == missed_task.id
        or task.id in scheduled_by_id
        or (
            task.scheduled_start is not None
            and replanning_engine._to_naive_local(
                task.scheduled_start
            ).date() == current_day
        )
    }
    for task in incomplete_tasks:
        if task.id not in affected_task_ids:
            continue
        scheduled_item = scheduled_by_id.get(task.id)
        if scheduled_item is None:
            task.scheduled_start = None
            task.scheduled_end = None
        else:
            old_start = task.scheduled_start
            old_end = task.scheduled_end
            schedule_changed = (
                old_start != scheduled_item.scheduled_start
                or old_end != scheduled_item.scheduled_end
            )
            task.scheduled_start = scheduled_item.scheduled_start
            task.scheduled_end = scheduled_item.scheduled_end
            if schedule_changed and old_start is not None and old_end is not None:
                db.add(
                    TaskHistory(
                        task_id=task.id,
                        user_id=current_user.id,
                        event_type="rescheduled",
                        old_start=old_start,
                        old_end=old_end,
                        new_start=scheduled_item.scheduled_start,
                        new_end=scheduled_item.scheduled_end,
                        reason="Schedule updated during replanning",
                    )
                )
    if recovery_open and missed_task_was_scheduled:
        scheduled_item = scheduled_by_id[missed_task.id]
        db.add(
            TaskHistory(
                task_id=missed_task.id,
                user_id=current_user.id,
                event_type="recovered",
                old_start=missed_start,
                old_end=missed_end,
                new_start=scheduled_item.scheduled_start,
                new_end=scheduled_item.scheduled_end,
                reason="Missed task was placed back into the schedule",
            )
        )
    for task in incomplete_tasks:
        task.schedule_needs_refresh = False
    db.commit()

    return ReplanResponse(
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
        missed_task_scheduled=missed_task_was_scheduled,
        scheduled_for=next(
            (
                item.scheduled_start
                for item in result.schedule
                if item.task_id == missed_task.id
            ),
            None,
        ),
    )
