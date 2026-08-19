from datetime import datetime

from pydantic import BaseModel


class TaskHistoryResponse(BaseModel):
    """A read-only lifecycle event for the History page."""

    id: int
    task_id: int
    task_title: str | None = None
    event_type: str
    timestamp: datetime
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    old_start: datetime | None = None
    old_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None
    reason: str | None = None


class HistoryEventResponse(BaseModel):
    """A meaningful, frontend-ready event from the append-only history."""

    id: int
    task_id: int
    task_title: str | None = None
    event_type: str
    timestamp: datetime
    old_start: datetime | None = None
    old_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None
    reason: str | None = None


class HistorySummaryResponse(BaseModel):
    completed: int
    missed: int
    recovered: int
    rescheduled: int
