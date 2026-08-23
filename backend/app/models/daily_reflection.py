from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyReflection(Base):
    """A user's editable reflection for one calendar day."""

    __tablename__ = "daily_reflections"
    __table_args__ = (
        UniqueConstraint("user_id", "reflection_date", name="uq_daily_reflection_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    reflection_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[str | None] = mapped_column(String, nullable=True)
    went_well: Mapped[str] = mapped_column(Text, default="", nullable=False)
    could_be_better: Mapped[str] = mapped_column(Text, default="", nullable=False)
    note_to_self: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tomorrow_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
