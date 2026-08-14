from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_or_404(task_id: int, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**task_data.model_dump())
    db.add(task)
    db.flush()
    db.add(TaskHistory(task_id=task.id, event_type="created"))
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).all()


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return get_task_or_404(task_id, db)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)
    was_completed = task.completed
    for field, value in task_data.model_dump().items():
        setattr(task, field, value)
    if not was_completed and task.completed:
        db.add(
            TaskHistory(
                task_id=task.id,
                event_type="completed",
                scheduled_start=task.scheduled_start,
                scheduled_end=task.scheduled_end,
            )
        )
    db.commit()
    db.refresh(task)
    return task


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
    db.commit()
