from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.planning import PlanRequest, PlanResponse, ScheduledTaskResponse
from app.services.planning import PlanningEngine

router = APIRouter(tags=["planning"])


@router.post("/plan", response_model=PlanResponse)
def create_plan(plan_request: PlanRequest, db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    result = PlanningEngine().generate_schedule(
        tasks,
        plan_request.available_start,
        plan_request.available_end,
    )

    for item in result.schedule:
        task = db.get(Task, item.task_id)
        if task is not None:
            task.scheduled_start = item.scheduled_start
            task.scheduled_end = item.scheduled_end
    db.commit()

    return PlanResponse(
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
    )
