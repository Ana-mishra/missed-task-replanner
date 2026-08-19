from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    deadline: datetime
    priority: str
    completed: bool = False
    status: Literal["pending", "completed", "missed"] = "pending"
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    energy_level: Literal["low", "medium", "high"] = "medium"
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    deadline_conflicted: bool = False

    @model_validator(mode="after")
    def validate_actual_duration(self):
        if self.actual_duration_minutes is not None and not self.completed:
            raise ValueError("actual_duration_minutes can only be provided for a completed task")
        if not self.completed and self.status == "completed":
            raise ValueError("status cannot be completed when completed is false")
        return self


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskResponse(TaskBase):
    id: int
    was_replanned: bool = False

    model_config = ConfigDict(from_attributes=True)
