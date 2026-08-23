from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.estimation import EstimationResponse
from app.services.estimation import EstimationService
from app.schemas.progress import ProgressResponse
from app.models.task_history import TaskHistory
from app.services.progress import ProgressService
from app.schemas.reflection import DailyReflectionInput, DailyReflectionResponse, WeeklyReflectionResponse
from app.services.reflection import ReflectionService
from app.models.daily_reflection import DailyReflection
from app.schemas.personalization import PersonalizationInsightResponse, PersonalizationResponse
from app.services.personalization import PersonalizationService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _daily_reflection_response(
    reflection: DailyReflection | None,
    selected_date: date,
    tasks: list[Task],
    history_records: list[TaskHistory],
) -> DailyReflectionResponse:
    glance = ReflectionService().daily_glance(tasks, history_records, selected_date)
    streak_days, recent_days = ReflectionService().reflection_streak(
        [], selected_date
    )
    # The caller fills the real persisted records below. Keeping this helper
    # focused on the selected day's task/history facts prevents a second
    # statistics system from growing beside weekly reflection analytics.
    return DailyReflectionResponse(
        date=selected_date,
        mood=reflection.mood if reflection else None,
        went_well=reflection.went_well if reflection else "",
        could_be_better=reflection.could_be_better if reflection else "",
        note_to_self=reflection.note_to_self if reflection else "",
        tomorrow_step=reflection.tomorrow_step if reflection else "",
        **glance,
        streak_days=streak_days,
        recent_streak_days=recent_days,
    )


def _build_daily_reflection_response(
    db: Session, current_user: User, selected_date: date
) -> DailyReflectionResponse:
    reflection = db.query(DailyReflection).filter(
        DailyReflection.user_id == current_user.id,
        DailyReflection.reflection_date == selected_date,
    ).first()
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    history_records = db.query(TaskHistory).filter(TaskHistory.user_id == current_user.id).all()
    response = _daily_reflection_response(reflection, selected_date, tasks, history_records)
    reflection_dates = [
        item.reflection_date
        for item in db.query(DailyReflection).filter(
            DailyReflection.user_id == current_user.id,
            DailyReflection.reflection_date <= selected_date,
        ).all()
    ]
    streak_days, recent_days = ReflectionService().reflection_streak(reflection_dates, selected_date)
    return response.model_copy(update={"streak_days": streak_days, "recent_streak_days": recent_days})


@router.get("/reflection/daily", response_model=DailyReflectionResponse)
def get_daily_reflection(
    reflection_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _build_daily_reflection_response(db, current_user, reflection_date or datetime.now().date())


@router.put("/reflection/daily", response_model=DailyReflectionResponse)
def save_daily_reflection(
    payload: DailyReflectionInput,
    reflection_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selected_date = reflection_date or datetime.now().date()
    reflection = db.query(DailyReflection).filter(
        DailyReflection.user_id == current_user.id,
        DailyReflection.reflection_date == selected_date,
    ).first()
    values = payload.model_dump()
    if reflection is None:
        reflection = DailyReflection(
            user_id=current_user.id, reflection_date=selected_date, **values
        )
        db.add(reflection)
    else:
        for field, value in values.items():
            setattr(reflection, field, value)
    db.commit()
    return _build_daily_reflection_response(db, current_user, selected_date)


@router.get("/estimation", response_model=EstimationResponse)
def get_estimation_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    completed_tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.completed.is_(True),
    ).all()
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
def get_progress_analytics(
    current_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    completed_history = db.query(TaskHistory).filter(
        TaskHistory.user_id == current_user.id,
        TaskHistory.event_type == "completed",
    ).all()
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
def get_weekly_reflection(
    week_start: date | None = None,
    period: Literal["week", "month", "all"] = "week",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_time = datetime.now()
    selected_week_start = week_start or (current_time.date() - timedelta(days=current_time.weekday()))
    if period == "month":
        selected_week_start = current_time.date().replace(day=1)
    elif period == "all":
        first_history_date = db.query(TaskHistory.timestamp).filter(
            TaskHistory.user_id == current_user.id,
        ).order_by(TaskHistory.timestamp.asc()).first()
        selected_week_start = (
            first_history_date[0].date()
            if first_history_date is not None
            else current_time.date()
        )
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    history_records = db.query(TaskHistory).filter(TaskHistory.user_id == current_user.id).all()
    result = ReflectionService().calculate(tasks, history_records, selected_week_start, current_time, period)
    return WeeklyReflectionResponse(
        week_start=result.week_start,
        week_end=result.week_end,
        tasks_created=result.tasks_created,
        tasks_completed=result.tasks_completed,
        tasks_missed=result.tasks_missed,
        tasks_replanned=result.tasks_replanned,
        tasks_recovered=result.tasks_recovered,
        completion_rate=result.completion_rate,
        estimated_completed_minutes=result.estimated_completed_minutes,
        actual_completed_minutes=result.actual_completed_minutes,
        average_estimation_difference_minutes=result.average_estimation_difference_minutes,
        postponement_cycles=result.postponement_cycles,
        most_productive_day=result.most_productive_day,
        daily_completed_tasks={day.isoformat(): count for day, count in result.daily_completed_tasks.items()},
        daily_planned_minutes={day.isoformat(): count for day, count in result.daily_planned_minutes.items()},
        daily_estimated_minutes={day.isoformat(): count for day, count in result.daily_estimated_minutes.items()},
        daily_actual_minutes={day.isoformat(): count for day, count in result.daily_actual_minutes.items()},
        progress_level=result.progress_level,
        progress_percent=result.progress_percent,
        previous_tasks_completed=result.previous_tasks_completed,
        previous_completion_rate=result.previous_completion_rate,
        previous_tasks_missed=result.previous_tasks_missed,
        previous_tasks_recovered=result.previous_tasks_recovered,
    )


@router.get("/personalization", response_model=PersonalizationResponse)
def get_personalization_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = PersonalizationService().analyze(
        db.query(Task).filter(Task.user_id == current_user.id).all(),
        db.query(TaskHistory).filter(TaskHistory.user_id == current_user.id).all(),
        datetime.now(),
    )
    return PersonalizationResponse(
        insights=[
            PersonalizationInsightResponse(
                type=insight.type,
                message=insight.message,
                evidence_count=insight.evidence_count,
                confidence=insight.confidence,
            )
            for insight in result
        ]
    )
