"""Browser reminder eligibility, Web Push delivery, and per-type evaluators.

Eligibility answers "should this user receive this type of browser
reminder?" from the stored UserSettings preference plus the presence of a
Web Push subscription. Delivery sends the push via pywebpush and records
idempotency in ReminderDelivery. The repeatable job entry point lives in
app.services.reminder_runner.
"""

import json
import logging
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT
from app.models.daily_reflection import DailyReflection
from app.models.push_subscription import PushSubscription
from app.models.reminder_delivery import ReminderDelivery
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.models.user_settings import UserSettings

logger = logging.getLogger(__name__)

ReminderType = Literal["planning", "missed_task", "reflection"]

_PREFERENCE_FIELD: dict[ReminderType, str] = {
    "planning": "planning_reminders",
    "missed_task": "missed_task_reminders",
    "reflection": "reflection_reminders",
}

VALID_REMINDER_TYPES = frozenset(_PREFERENCE_FIELD)

# Hour in Asia/Kolkata from which the daily planning reminder becomes due.
PLANNING_REMINDER_HOUR = 8

# Server-wide reminder timezone. Planora persists no per-user timezone and
# Railway Cron schedules fire in UTC, so all reminder wall-clock decisions
# (planning date, 08:00 gate, ISO week) are explicitly evaluated in
# Asia/Kolkata, Planora's current target deployment region. No per-user
# timezone architecture is introduced here.
REMINDER_TIMEZONE = ZoneInfo("Asia/Kolkata")


def planora_now(now: datetime | None = None) -> datetime:
    """Return `now` expressed in the reminder timezone.

    None means the current moment. Aware datetimes are converted; naive
    datetimes are already Planora wall-clock time (server timestamps and
    existing callers use naive local values) and are simply tagged.
    """
    if now is None:
        return datetime.now(REMINDER_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=REMINDER_TIMEZONE)
    return now.astimezone(REMINDER_TIMEZONE)

PAYLOADS: dict[ReminderType, dict[str, str]] = {
    "planning": {
        "title": "Planora",
        "body": "Your day is ready to be planned.",
        "tag": "planora-planning",
        "url": "/?page=plan",
    },
    "missed_task": {
        "title": "Planora",
        "body": "You have a missed task that needs a reset.",
        "tag": "planora-missed-task",
        "url": "/",
    },
    "reflection": {
        "title": "Planora",
        "body": "Your weekly reflection is ready.",
        "tag": "planora-reflection",
        "url": "/?page=reflection",
    },
}


def should_send_browser_reminder(db: Session, user: User, reminder_type: ReminderType) -> bool:
    """Return True only when the preference is ON and a subscription exists."""
    field = _PREFERENCE_FIELD.get(reminder_type)
    if field is None:
        return False
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if settings is None:
        # No explicit settings row yet: defaults are all ON, but without a
        # push subscription there is nowhere to deliver to.
        has_subscription = (
            db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()
            is not None
        )
        return bool(has_subscription)
    if not getattr(settings, field, False):
        return False
    return (
        db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()
        is not None
    )


def get_push_subscription(db: Session, user: User) -> PushSubscription | None:
    """Return the current user's push subscription, if any."""
    return db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()


def vapid_configured() -> bool:
    """Return True when Web Push delivery is configured."""
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def already_delivered(db: Session, user_id: int, reminder_type: str, period_key: str) -> bool:
    return (
        db.query(ReminderDelivery)
        .filter(
            ReminderDelivery.user_id == user_id,
            ReminderDelivery.reminder_type == reminder_type,
            ReminderDelivery.period_key == period_key,
        )
        .first()
        is not None
    )


def record_delivery(db: Session, user_id: int, reminder_type: str, period_key: str) -> None:
    """Record a delivery idempotently; concurrent duplicates are ignored."""
    if already_delivered(db, user_id, reminder_type, period_key):
        return
    db.add(
        ReminderDelivery(
            user_id=user_id,
            reminder_type=reminder_type,
            period_key=period_key,
            sent_at=datetime.now(),
            status="sent",
        )
    )
    db.commit()


def send_web_push(db: Session, user: User, payload: dict[str, str]) -> bool:
    """Send one Web Push notification; fail safely without crashing.

    Returns True on success. Missing VAPID config or a missing
    subscription returns False. Permanently failed subscriptions
    (HTTP 404/410 from the push service) are removed. Unexpected errors
    are logged and return False so one bad push never breaks the whole
    scheduler run.
    """
    subscription = get_push_subscription(db, user)
    if subscription is None:
        return False
    if not vapid_configured():
        logger.warning("Skipping browser push for user %s: VAPID keys not configured", user.id)
        return False
    try:
        from pywebpush import Vapid, WebPushException, webpush
    except ImportError:
        logger.warning("Skipping browser push for user %s: pywebpush not installed", user.id)
        return False
    vapid_key = VAPID_PRIVATE_KEY.strip()
    if "BEGIN" in vapid_key:
        # Operators store the PEM block in the env var; pywebpush string
        # keys only accept raw/DER, so normalize PEM to a Vapid instance
        # (which webpush also accepts) instead of failing at send time.
        try:
            vapid_key = Vapid.from_pem(vapid_key.encode())
        except Exception:
            logger.exception("Invalid VAPID private key PEM; skipping browser push")
            return False
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=vapid_key,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except Exception as exc:  # noqa: BLE001 - push failures must not break the run
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in (404, 410):
            logger.info(
                "Removing expired push subscription for user %s (push service %s)",
                user.id,
                status_code,
            )
            db.delete(subscription)
            db.commit()
            return False
        logger.exception("Browser push failed for user %s", user.id)
        return False


def send_browser_reminder(
    db: Session, user: User, reminder_type: ReminderType, period_key: str
) -> bool:
    """Check preference + subscription, send the push, record delivery."""
    if reminder_type not in VALID_REMINDER_TYPES:
        return False
    if already_delivered(db, user.id, reminder_type, period_key):
        return False
    if not should_send_browser_reminder(db, user, reminder_type):
        return False
    if send_web_push(db, user, PAYLOADS[reminder_type]):
        record_delivery(db, user.id, reminder_type, period_key)
        return True
    return False


def planning_period_key(now: datetime) -> str:
    return planora_now(now).date().isoformat()


def reflection_period_key(now: datetime) -> str:
    year, week, _ = planora_now(now).date().isocalendar()
    return f"{year}-W{week:02d}"


def missed_period_key(history_id: int) -> str:
    return f"missed-history-{history_id}"


def user_has_plannable_tasks(db: Session, user: User) -> bool:
    """True when incomplete tasks exist that could go into a plan."""
    return (
        db.query(Task.id)
        .filter(Task.user_id == user.id, Task.completed.is_(False))
        .first()
        is not None
    )


def user_already_planned_today(db: Session, user: User, now: datetime) -> bool:
    """True when the user already has a plan for today.

    Either a task was scheduled today (a 'scheduled' history event with
    today's timestamp) or every incomplete task already holds a complete
    persisted slot with nothing flagged for refresh — the same "already
    planned" notion the /plan idempotency guard relies on. The day boundary
    is evaluated in Asia/Kolkata.
    """
    local = planora_now(now)
    day_start = datetime.combine(local.date(), datetime.min.time())
    scheduled_today = (
        db.query(TaskHistory.id)
        .filter(
            TaskHistory.user_id == user.id,
            TaskHistory.event_type == "scheduled",
            TaskHistory.timestamp >= day_start,
        )
        .first()
    )
    if scheduled_today is not None:
        return True
    incomplete = db.query(Task).filter(Task.user_id == user.id, Task.completed.is_(False)).all()
    if not incomplete:
        return False
    return all(
        task.scheduled_start is not None
        and task.scheduled_end is not None
        and not task.schedule_needs_refresh
        for task in incomplete
    )


def user_reflected_this_week(db: Session, user: User, now: datetime) -> bool:
    """True when the user saved any daily reflection in this ISO week (Asia/Kolkata)."""
    local = planora_now(now)
    year, week, _ = local.date().isocalendar()
    reflections = (
        db.query(DailyReflection.reflection_date)
        .filter(DailyReflection.user_id == user.id)
        .all()
    )
    return any(
        (row[0].isocalendar()[0], row[0].isocalendar()[1]) == (year, week) for row in reflections
    )


def evaluate_planning_reminder(db: Session, user: User, now: datetime) -> bool:
    """Send today's planning reminder when all conditions hold.

    The 08:00 gate and the delivery date use Asia/Kolkata wall-clock time.
    """
    local = planora_now(now)
    if local.hour < PLANNING_REMINDER_HOUR:
        return False
    if not user_has_plannable_tasks(db, user):
        return False
    if user_already_planned_today(db, user, local):
        return False
    return send_browser_reminder(db, user, "planning", planning_period_key(local))


def evaluate_missed_reminders(db: Session, user: User) -> int:
    """Send at most one notification per NEW 'missed' history event.

    Only event_type == 'missed' qualifies; 'overdue' never triggers a
    reminder. Consumes existing lifecycle rows without writing new ones.
    Returns the number of notifications sent.
    """
    if not should_send_browser_reminder(db, user, "missed_task"):
        return 0
    missed_events = (
        db.query(TaskHistory)
        .filter(TaskHistory.user_id == user.id, TaskHistory.event_type == "missed")
        .order_by(TaskHistory.id.asc())
        .all()
    )
    sent = 0
    for event in missed_events:
        try:
            if send_browser_reminder(db, user, "missed_task", missed_period_key(event.id)):
                sent += 1
        except Exception:  # noqa: BLE001 - one bad event must not stop the rest
            logger.exception("Missed-task reminder failed for user %s event %s", user.id, event.id)
    return sent


def evaluate_reflection_reminder(db: Session, user: User, now: datetime) -> bool:
    """Send this week's reflection reminder once, unless already reflected.

    The ISO week is evaluated in Asia/Kolkata.
    """
    local = planora_now(now)
    if user_reflected_this_week(db, user, local):
        return False
    return send_browser_reminder(db, user, "reflection", reflection_period_key(local))
