from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.postponement import PostponementResponse
from app.services.postponement import PostponementService

router = APIRouter(tags=["postponement"])


@router.get("/tasks/{task_id}/postponement", response_model=PostponementResponse)
def get_postponement_analysis(
    task_id: int,
    threshold: int = Query(default=3, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    history_records = (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.timestamp, TaskHistory.id)
        .all()
    )
    result = PostponementService().analyze(task_id, history_records, threshold)
    return PostponementResponse(
        task_id=result.task_id,
        postponement_count=result.postponement_count,
        last_postponed_at=result.last_postponed_at,
        needs_review=result.needs_review,
    )
