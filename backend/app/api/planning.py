from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
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
        plan_request.energy_level,
        plan_request.bad_day,
    )

    scheduled_task_ids = {item.task_id for item in result.schedule}
    for item in result.schedule:
        task = db.get(Task, item.task_id)
        if task is not None:
            schedule_changed = (
                task.scheduled_start != item.scheduled_start
                or task.scheduled_end != item.scheduled_end
            )
            task.scheduled_start = item.scheduled_start
            task.scheduled_end = item.scheduled_end
            if schedule_changed:
                db.add(
                    TaskHistory(
                        task_id=task.id,
                        event_type="scheduled",
                        scheduled_start=item.scheduled_start,
                        scheduled_end=item.scheduled_end,
                    )
                )
    for task in tasks:
        if not task.completed and task.id not in scheduled_task_ids:
            task.scheduled_start = None
            task.scheduled_end = None
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
        bad_day=result.bad_day,
    )
