from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserSettings(Base):
    """Per-user preferences, kept separate from core identity on User."""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    theme: Mapped[str] = mapped_column(String, default="light", server_default="light", nullable=False)
    planning_reminders: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    missed_task_reminders: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    reflection_reminders: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="settings")
