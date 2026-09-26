from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.event_time import as_utc_aware


def _serialize_event_instant(value: datetime | None) -> datetime | None:
    """Emit an event instant with explicit UTC timezone info (``...Z``).

    Stored rows are naive UTC wall-clock (including all pre-fix history, as
    production runs in UTC), so naive values are interpreted as UTC without
    shifting the instant. Schedule fields (``scheduled_start/end``,
    ``old/new_start/end``, ``deadline``) intentionally have no serializer:
    they remain naive user wall-clock values.
    """
    return as_utc_aware(value)


class TaskHistoryResponse(BaseModel):
    """A read-only lifecycle event for the History page."""

    id: int
    task_id: int | None
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

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> datetime:
        return _serialize_event_instant(value)


class HistoryEventResponse(BaseModel):
    """A meaningful, frontend-ready event from the append-only history."""

    id: int
    task_id: int | None
    task_title: str | None = None
    event_type: str
    timestamp: datetime
    deadline: datetime | None = None
    old_start: datetime | None = None
    old_end: datetime | None = None
    new_start: datetime | None = None
    new_end: datetime | None = None
    reason: str | None = None
    task_count: int | None = None
    completed_at: datetime | None = None

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> datetime:
        return _serialize_event_instant(value)

    @field_serializer("completed_at")
    def serialize_completed_at(self, value: datetime | None) -> datetime | None:
        return _serialize_event_instant(value)


class HistorySummaryResponse(BaseModel):
    completed: int
    missed: int
    recovered: int
    rescheduled: int
