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

MeaningfulEvent = Literal["scheduled","completed", "missed", "overdue", "rescheduled", "recovered"]
HistoryRange = Literal["week", "month", "year", "all"]
# Scheduled is shown in the All feed but intentionally has no dedicated tab
# or summary card.
MEANINGFUL_EVENT_TYPES = {
    "scheduled",
    "completed",
    "missed",
    "overdue",
    "rescheduled",
    "recovered",
}
INTERNAL_RESCHEDULE_REASONS = {
    "Plan reshaped",
    "Schedule updated by planning",
    "Schedule updated during replanning",
}


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
        db.query(TaskHistory, Task.title, Task.completed_at, Task.deadline)
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
    for record, title, completed_at, deadline in rows:
        resolved_type = record.event_type
        if resolved_type not in MEANINGFUL_EVENT_TYPES:
            continue
        if start is not None and record.timestamp < start:
            continue
        if end is not None and record.timestamp >= end:
            continue
        if event_type is not None and resolved_type != event_type:
            continue
        old_start = record.old_start
        old_end = record.old_end
        new_start = record.new_start or record.scheduled_start
        new_end = record.new_end or record.scheduled_end
        # Older databases can contain no-op rows from previous planner runs.
        # They remain in the append-only audit table, but are not a meaningful
        # user-facing change.
        if (
            resolved_type == "rescheduled"
            and old_start is not None
            and old_end is not None
            and old_start == new_start
            and old_end == new_end
        ):
            continue
        events.append(
            HistoryEventResponse(
                id=record.id,
                task_id=record.task_id,
                task_title=title,
                event_type=resolved_type,
                timestamp=record.timestamp,
                deadline=deadline,
                old_start=old_start,
                old_end=old_end,
                new_start=new_start,
                new_end=new_end,
                reason=record.reason,
                completed_at=completed_at if resolved_type == "completed" else None,
            )
        )
    return list(reversed(_group_plan_reshapes(events)))


def _group_plan_reshapes(events: list[HistoryEventResponse]) -> list[HistoryEventResponse]:
    """Present one plan-wide change rather than one row per moved task.

    The original task-level rows remain available to analytics in
    ``task_history``. New planner writes share an exact timestamp; older
    internal rows are grouped by their displayed minute for a useful, compact
    history story.
    """
    grouped: dict[tuple[datetime, str], list[HistoryEventResponse]] = {}
    ungrouped: list[HistoryEventResponse] = []
    for event in events:
        if event.event_type != "rescheduled" or event.reason not in INTERNAL_RESCHEDULE_REASONS:
            ungrouped.append(event)
            continue
        timestamp = event.timestamp if event.reason == "Plan reshaped" else event.timestamp.replace(second=0, microsecond=0)
        grouped.setdefault((timestamp, event.reason), []).append(event)

    for (timestamp, _), grouped_events in grouped.items():
        first = grouped_events[0]
        count = len(grouped_events)
        if count == 1:
            ungrouped.append(first.model_copy(update={"reason": None}))
            continue
        ungrouped.append(
            first.model_copy(
                update={
                    "timestamp": timestamp,
                    "task_title": "Plan reshaped",
                    "reason": f"{count} tasks were rearranged to fit your day.",
                    "task_count": count,
                    "old_start": None,
                    "old_end": None,
                    "new_start": None,
                    "new_end": None,
                }
            )
        )
    return sorted(ungrouped, key=lambda event: (event.timestamp, event.id))


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
    inclusive at the date level. First-time ``scheduled`` events appear in
    the All feed; the selectable filters remain the user-facing categories.
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
