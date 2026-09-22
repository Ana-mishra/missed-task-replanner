from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReminderDelivery(Base):
    """Idempotency record for one delivered browser reminder.

    ``(user_id, reminder_type, period_key)`` is unique so each logical
    reminder is delivered at most once no matter how often the reminder
    job runs. ``period_key`` is the calendar day (planning), the
    TaskHistory id (missed-task), or the ISO week (reflection).
    """

    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "reminder_type", "period_key",
            name="uq_reminder_delivery_user_type_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reminder_type: Mapped[str] = mapped_column(String, nullable=False)
    period_key: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    status: Mapped[str] = mapped_column(String, default="sent", nullable=False)
