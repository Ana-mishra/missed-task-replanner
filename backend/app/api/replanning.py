from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.planning import PlanRequest, ScheduledTaskResponse
from app.schemas.replanning import ReplanResponse
from app.services.replanning import ReplanningEngine

router = APIRouter(tags=["replanning"])


@router.post("/replan/{task_id}", response_model=ReplanResponse)
def replan_task(task_id: int, replan_request: PlanRequest, db: Session = Depends(get_db)):
    missed_task = db.get(Task, task_id)
    if missed_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if missed_task.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed tasks cannot be replanned",
        )

    missed_task.status = "missed"
    missed_task.completed = False
    incomplete_tasks = db.query(Task).filter(Task.completed.is_(False)).all()
    result = ReplanningEngine().generate_revised_schedule(
        incomplete_tasks,
        missed_task,
        replan_request.available_start,
        replan_request.available_end,
    )

    scheduled_by_id = {item.task_id: item for item in result.schedule}
    for task in incomplete_tasks:
        scheduled_item = scheduled_by_id.get(task.id)
        if scheduled_item is None:
            task.scheduled_start = None
            task.scheduled_end = None
        else:
            task.scheduled_start = scheduled_item.scheduled_start
            task.scheduled_end = scheduled_item.scheduled_end
    db.commit()

    return ReplanResponse(
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
