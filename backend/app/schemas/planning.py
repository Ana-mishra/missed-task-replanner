from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class PlanRequest(BaseModel):
    available_start: datetime
    available_end: datetime
    energy_level: Literal["low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.available_end < self.available_start:
            raise ValueError("available_end must be after available_start")
        return self


class ScheduledTaskResponse(BaseModel):
    task_id: int
    title: str
    scheduled_start: datetime
    scheduled_end: datetime


class PlanResponse(BaseModel):
    schedule: list[ScheduledTaskResponse]
    is_overloaded: bool
    unscheduled_minutes: int
