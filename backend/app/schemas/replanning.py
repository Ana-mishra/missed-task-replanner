from datetime import datetime

from pydantic import BaseModel

from app.schemas.planning import ScheduledTaskResponse


class ReplanResponse(BaseModel):
    schedule: list[ScheduledTaskResponse]
    is_overloaded: bool
    unscheduled_minutes: int
    missed_task_scheduled: bool
    scheduled_for: datetime | None = None
