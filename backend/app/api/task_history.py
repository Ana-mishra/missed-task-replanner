from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.task_history import TaskHistoryResponse

router = APIRouter(prefix="/task-history", tags=["task-history"])


@router.get("", response_model=list[TaskHistoryResponse])
def list_task_history(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Return the append-only task timeline, newest events first.

    Deleted-task history remains visible because ownership is copied to every
    lifecycle event when it is recorded.
    """
    rows = (
        db.query(TaskHistory, Task.title)
        .outerjoin(Task, Task.id == TaskHistory.task_id)
        .filter(
            or_(
                TaskHistory.user_id == current_user.id,
                and_(TaskHistory.user_id.is_(None), Task.user_id == current_user.id),
            )
        )
        .order_by(TaskHistory.timestamp.desc(), TaskHistory.id.desc())
        .all()
    )
    return [
        TaskHistoryResponse(
            id=event.id,
            task_id=event.task_id,
            task_title=title,
            event_type=event.event_type,
            timestamp=event.timestamp,
            scheduled_start=event.scheduled_start,
            scheduled_end=event.scheduled_end,
            old_start=event.old_start,
            old_end=event.old_end,
            new_start=event.new_start,
            new_end=event.new_end,
            reason=event.reason,
        )
        for event, title in rows
    ]
