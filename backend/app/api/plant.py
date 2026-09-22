"""GET /plant — My Plant data endpoint.

Returns plant growth and vitality state derived from the authenticated
user's task completion history.  The endpoint is read-only; no new events
are written.  All calculations use IST (Asia/Kolkata) calendar dates.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models.task_history import TaskHistory
from app.models.user import User
from app.schemas.plant import PlantResponse
from app.services.plant import PlantService

router = APIRouter(prefix="/plant", tags=["plant"])


@router.get("", response_model=PlantResponse)
def get_plant(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlantResponse:
    """Return the authenticated user's plant state.

    Fetches only ``event_type == 'completed'`` history rows so the query
    stays narrow and the service layer does not need to filter again.
    """
    completed_history = (
        db.query(TaskHistory)
        .filter(
            TaskHistory.user_id == current_user.id,
            TaskHistory.event_type == "completed",
        )
        .all()
    )

    result = PlantService().calculate(completed_history)

    return PlantResponse(
        growth_days=result.growth_days,
        stage=result.stage,
        stage_progress=result.stage_progress,
        current_streak_days=result.current_streak_days,
        days_since_last_growth=result.days_since_last_growth,
        completed_today=result.completed_today,
        grew_today=result.grew_today,
        vitality=result.vitality,
    )
