from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.estimation import EstimationResponse
from app.services.estimation import EstimationService
from app.schemas.progress import ProgressResponse
from app.models.task_history import TaskHistory
from app.services.progress import ProgressService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/estimation", response_model=EstimationResponse)
def get_estimation_analytics(db: Session = Depends(get_db)):
    completed_tasks = db.query(Task).filter(Task.completed.is_(True)).all()
    result = EstimationService().calculate(completed_tasks)
    return EstimationResponse(
        completed_tasks=result.completed_tasks,
        estimated_minutes=result.estimated_minutes,
        actual_minutes=result.actual_minutes,
        total_difference_minutes=result.total_difference_minutes,
        average_difference_minutes=result.average_difference_minutes,
        average_accuracy_percent=result.average_accuracy_percent,
        tendency=result.tendency,
    )


@router.get("/progress", response_model=ProgressResponse)
def get_progress_analytics(current_date: date | None = None, db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    completed_history = db.query(TaskHistory).filter(TaskHistory.event_type == "completed").all()
    result = ProgressService().calculate(tasks, completed_history, current_date or date.today())
    return ProgressResponse(
        completed_tasks=result.completed_tasks,
        completed_minutes=result.completed_minutes,
        estimated_completed_minutes=result.estimated_completed_minutes,
        completion_rate=result.completion_rate,
        current_streak_days=result.current_streak_days,
        progress_level=result.progress_level,
        progress_percent=result.progress_percent,
    )
