from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskResponse(TaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
