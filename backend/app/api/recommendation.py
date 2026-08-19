from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation import RecommendationEngine

router = APIRouter(tags=["recommendation"])


@router.get("/recommend", response_model=RecommendationResponse)
def recommend_task(
    current_time: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    result = RecommendationEngine().recommend(tasks, current_time or datetime.now())
    return RecommendationResponse(recommended_task=result.task, reason=result.reason)
