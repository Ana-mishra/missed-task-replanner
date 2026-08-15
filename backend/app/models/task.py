from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="valid_duration_minutes"),
        CheckConstraint("status IN ('pending', 'completed', 'missed')", name="valid_task_status"),
        CheckConstraint("energy_level IN ('low', 'medium', 'high')", name="valid_energy_level"),
        CheckConstraint(
            "actual_duration_minutes IS NULL OR actual_duration_minutes > 0",
            name="valid_actual_duration_minutes",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", nullable=False)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    energy_level: Mapped[str] = mapped_column(String, default="medium", server_default="medium", nullable=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_conflicted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    history_records: Mapped[list["TaskHistory"]] = relationship(
        back_populates="task",
        passive_deletes=True,
    )
