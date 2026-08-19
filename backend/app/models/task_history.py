from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskHistory(Base):
    """An append-only record of important Task lifecycle events."""

    __tablename__ = "task_history"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'scheduled', 'missed', 'completed', "
            "'replanned', 'rescheduled', 'recovered', 'deleted')",
            name="valid_task_history_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    # Stored separately so a deleted task's append-only history remains
    # private to its owner after the Task row is gone.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
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
