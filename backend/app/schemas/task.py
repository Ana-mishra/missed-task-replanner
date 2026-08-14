from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    duration_minutes: int
    deadline: datetime
    priority: str
    completed: bool = False
    status: Literal["pending", "completed", "missed"] = "pending"
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    energy_level: Literal["low", "medium", "high"] = "medium"
    actual_duration_minutes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_actual_duration(self):
        if self.actual_duration_minutes is not None and not self.completed:
            raise ValueError("actual_duration_minutes can only be provided for a completed task")
        return self


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskResponse(TaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
