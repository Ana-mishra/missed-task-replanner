"""Read-only, user-facing task history endpoints."""

from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.task_history import HistoryEventResponse, HistorySummaryResponse

router = APIRouter(prefix="/history", tags=["history"])

MeaningfulEvent = Literal["completed", "missed", "rescheduled", "recovered"]
HistoryRange = Literal["week", "month", "year", "all"]
MEANINGFUL_EVENT_TYPES = {"completed", "missed", "rescheduled", "recovered"}


def range_start(value: HistoryRange, now: datetime | None = None) -> datetime | None:
    """Return the server-local start of a named calendar range."""
    if value == "all":
        return None
    now = now or datetime.now()
    today = now.date()
    if value == "week":
        return datetime.combine(today - timedelta(days=today.weekday()), time.min)
    if value == "month":
        return datetime(now.year, now.month, 1)
    return datetime(now.year, 1, 1)


def load_meaningful_history(
    db: Session,
    user_id: int,
    history_range: HistoryRange,
    event_type: MeaningfulEvent | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[HistoryEventResponse]:
    """Load meaningful events while keeping old ``replanned`` rows usable.

    ``replanned`` was the original event name. New writes use the clearer
    rescheduled/recovered pair. Legacy rows remain available through the
    compatibility endpoint but are excluded here because their older payload
    lacks enough before/after context to present trustworthy user history.
    """
    query = (
        db.query(TaskHistory, Task.title)
        .outerjoin(Task, Task.id == TaskHistory.task_id)
        .filter(
            or_(
                TaskHistory.user_id == user_id,
                and_(TaskHistory.user_id.is_(None), Task.user_id == user_id),
            )
        )
    )
    start = datetime.combine(start_date, time.min) if start_date else range_start(history_range)
    end = datetime.combine(end_date + timedelta(days=1), time.min) if end_date else None
    # Load the full stream first so a legacy replanned event can still be
    # recognised as a recovery when its missed event predates the filter.
    rows = query.order_by(TaskHistory.timestamp, TaskHistory.id).all()
    events: list[HistoryEventResponse] = []
    for record, title in rows:
        resolved_type = record.event_type
        if resolved_type not in MEANINGFUL_EVENT_TYPES:
            continue
        if start is not None and record.timestamp < start:
            continue
        if end is not None and record.timestamp >= end:
            continue
        if event_type is not None and resolved_type != event_type:
            continue
        events.append(
            HistoryEventResponse(
                id=record.id,
                task_id=record.task_id,
                task_title=title,
                event_type=resolved_type,
                timestamp=record.timestamp,
                old_start=record.old_start,
                old_end=record.old_end,
                new_start=record.new_start or record.scheduled_start,
                new_end=record.new_end or record.scheduled_end,
                reason=record.reason,
            )
        )
    return list(reversed(events))


@router.get("", response_model=list[HistoryEventResponse])
def list_history(
    event_type: MeaningfulEvent | None = None,
    range: HistoryRange = "all",
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return filtered, meaningful history newest first.

    Explicit dates take precedence over the named calendar range and are
    inclusive at the date level. Ordinary planner ``scheduled`` events are
    intentionally excluded.
    """
    return load_meaningful_history(db, current_user.id, range, event_type, start_date, end_date)


@router.get("/summary", response_model=HistorySummaryResponse)
def history_summary(
    range: HistoryRange = "all",
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return meaningful event counts for the same selected history period."""
    events = load_meaningful_history(
        db, current_user.id, range, start_date=start_date, end_date=end_date
    )
    return HistorySummaryResponse(
        completed=sum(event.event_type == "completed" for event in events),
        missed=sum(event.event_type == "missed" for event in events),
        recovered=sum(event.event_type == "recovered" for event in events),
        rescheduled=sum(event.event_type == "rescheduled" for event in events),
    )
