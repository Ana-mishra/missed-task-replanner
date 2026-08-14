from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.estimation import EstimationResponse
from app.services.estimation import EstimationService
from app.schemas.progress import ProgressResponse
from app.models.task_history import TaskHistory
from app.services.progress import ProgressService
from app.schemas.reflection import WeeklyReflectionResponse
from app.services.reflection import ReflectionService

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
    server_now = datetime.now()
    selected_date = current_date or server_now.date()
    selected_time = server_now if current_date is None else datetime.combine(current_date, datetime.max.time())
    result = ProgressService().calculate(tasks, completed_history, selected_date, selected_time)
    return ProgressResponse(
        completed_tasks=result.completed_tasks,
        completed_minutes=result.completed_minutes,
        estimated_completed_minutes=result.estimated_completed_minutes,
        completion_rate=result.completion_rate,
        current_streak_days=result.current_streak_days,
        progress_level=result.progress_level,
        progress_percent=result.progress_percent,
    )


@router.get("/reflection/weekly", response_model=WeeklyReflectionResponse)
def get_weekly_reflection(week_start: date | None = None, db: Session = Depends(get_db)):
    current_time = datetime.now()
    selected_week_start = week_start or (current_time.date() - timedelta(days=current_time.weekday()))
    tasks = db.query(Task).all()
    history_records = db.query(TaskHistory).all()
    result = ReflectionService().calculate(tasks, history_records, selected_week_start, current_time)
    return WeeklyReflectionResponse(
        week_start=result.week_start,
        week_end=result.week_end,
        tasks_created=result.tasks_created,
        tasks_completed=result.tasks_completed,
        tasks_missed=result.tasks_missed,
        tasks_replanned=result.tasks_replanned,
        completion_rate=result.completion_rate,
        estimated_completed_minutes=result.estimated_completed_minutes,
        actual_completed_minutes=result.actual_completed_minutes,
        average_estimation_difference_minutes=result.average_estimation_difference_minutes,
        postponement_cycles=result.postponement_cycles,
        most_productive_day=result.most_productive_day,
        daily_completed_tasks={day.isoformat(): count for day, count in result.daily_completed_tasks.items()},
        progress_level=result.progress_level,
        progress_percent=result.progress_percent,
    )
