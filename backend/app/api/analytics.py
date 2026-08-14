from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.estimation import EstimationResponse
from app.services.estimation import EstimationService

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
