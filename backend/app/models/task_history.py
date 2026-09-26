from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.event_time import utcnow_naive

if TYPE_CHECKING:
    from app.models.task import Task


class TaskHistory(Base):
    """An append-only record of important Task lifecycle events."""

    __tablename__ = "task_history"
    __table_args__ = (
        CheckConstraint(
    "event_type IN ('created', 'scheduled', 'missed', 'overdue', 'completed', "
"'replanned', 'rescheduled', 'recovered', 'deleted')",
    name="valid_task_history_event_type",
),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nullable so a deleted task's history survives it: the database clears
    # task_id (ON DELETE SET NULL) while user_id keeps the rows private to
    # their owner, exactly as the append-only History contract requires.
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    # Stored separately so a deleted task's append-only history remains
    # private to its owner after the Task row is gone.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Display-only snapshot of the task title at event time, so analytics
    # (e.g. Plan Stability tooltips) can name tasks whose rows were later
    # deleted. Never used for logic, grouping, or classification; old rows
    # simply have NULL here.
    task_title: Mapped[str | None] = mapped_column(String, nullable=True)
    # Event instant in UTC. The column stays naive (UTC wall-clock, the same
    # bytes as before, so existing rows need no migration); the API boundary
    # interprets it as UTC and serializes it with explicit timezone info.
    # Schedule fields below remain user wall-clock and are never UTC.
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Keep the legacy scheduled_* fields for existing API clients.  The
    # explicit before/after fields make schedule changes understandable later.
    old_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    old_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="history_records")
