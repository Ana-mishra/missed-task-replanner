from pydantic import BaseModel

from app.schemas.planning import ScheduledTaskResponse


class ReplanResponse(BaseModel):
    schedule: list[ScheduledTaskResponse]
    is_overloaded: bool
    unscheduled_minutes: int
