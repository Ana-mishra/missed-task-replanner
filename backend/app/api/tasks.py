from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.history_state import recovery_state_by_task_id

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_or_404(task_id: int, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def serialize_task(task: Task, replanned_task_ids: set[int] | None = None) -> TaskResponse:
    """Add response-only lifecycle information without storing it on Task."""
    if replanned_task_ids is None:
        replanned_task_ids = set()
    return TaskResponse.model_validate(task).model_copy(
        update={"was_replanned": task.id in replanned_task_ids}
    )


def get_replanned_task_ids(db: Session, task_ids: list[int] | None = None) -> set[int]:
    recovered_task_ids, _ = recovery_state_by_task_id(db, task_ids)
    return recovered_task_ids


def to_naive_local(value: datetime) -> datetime:
    """Use the same aware/naive comparison convention as the planners."""
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value


def is_deadline_protected(task: Task, db: Session) -> bool:
    """Keep the original deadline for work that has entered the missed flow."""
    if task.completed:
        return False
    return (
        task.status == "missed"
        or task.id in get_replanned_task_ids(db, [task.id])
        or to_naive_local(task.deadline) < datetime.now()
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**task_data.model_dump())
    if task.completed:
        task.status = "completed"
    db.add(task)
    db.flush()
    db.add(TaskHistory(task_id=task.id, event_type="created"))
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    replanned_task_ids = get_replanned_task_ids(db, [task.id for task in tasks])
    return [serialize_task(task, replanned_task_ids) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)
    return serialize_task(task, get_replanned_task_ids(db, [task.id]))


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)
    if (
        is_deadline_protected(task, db)
        and to_naive_local(task_data.deadline) != to_naive_local(task.deadline)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The deadline is protected after a task is missed, overdue, or replanned",
        )
    was_completed = task.completed
    update_data = task_data.model_dump()
    if was_completed:
        update_data.pop("actual_duration_minutes")
    planning_fields = ("duration_minutes", "deadline", "priority", "energy_level")
    schedule_needs_refresh = not task.completed and any(
        getattr(task, field) != update_data[field] for field in planning_fields
    )
    if task_data.completed:
        update_data["status"] = "completed"
    for field, value in update_data.items():
        setattr(task, field, value)
    if schedule_needs_refresh and not task.completed:
        task.scheduled_start = None
        task.scheduled_end = None
        task.schedule_needs_refresh = True
    if not was_completed and task.completed:
        task.status = "completed"
        db.add(
            TaskHistory(
                task_id=task.id,
                event_type="completed",
                scheduled_start=task.scheduled_start,
                scheduled_end=task.scheduled_end,
                old_start=task.scheduled_start,
                old_end=task.scheduled_end,
                reason="Task marked completed",
            )
        )
    db.commit()
    db.refresh(task)
    return serialize_task(task, get_replanned_task_ids(db, [task.id]))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)
    db.add(
        TaskHistory(
            task_id=task.id,
            event_type="deleted",
            scheduled_start=task.scheduled_start,
            scheduled_end=task.scheduled_end,
        )
    )
    db.commit()
    db.delete(task)
    for remaining_task in db.query(Task).filter(Task.completed.is_(False)).all():
        remaining_task.schedule_needs_refresh = True
    db.commit()
