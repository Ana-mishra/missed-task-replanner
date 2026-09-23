from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class PlanRequest(BaseModel):
    available_start: datetime
    available_end: datetime
    energy_level: Literal["low", "medium", "high"] | None = None
    bad_day: bool = False
    force_replan: bool = False
    # IANA timezone name from the browser (e.g. "Asia/Kolkata"). The
    # persisted schedule is stored/displayed as naive wall-clock values in
    # the user's frame, so the backend needs this to interpret an aware
    # request timestamp in that same frame. Absent for backward
    # compatibility with naive-datetime callers.
    timezone: str | None = None

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
    reason: str = ""


class PlanResponse(BaseModel):
    schedule: list[ScheduledTaskResponse]
    is_overloaded: bool
    unscheduled_minutes: int
    bad_day: bool
    bad_day_protected_count: int = 0
    bad_day_capacity_minutes: int = 0
    schedule_refresh_reason: str = ""
