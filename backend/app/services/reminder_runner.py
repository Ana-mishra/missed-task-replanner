"""Repeatable browser-reminder job entry point for Railway Cron.

TIMEZONE: Planora persists no per-user timezone, and Railway Cron fires in
UTC. All reminder wall-clock decisions (planning date, the 08:00 gate, ISO
week) are explicitly evaluated in Asia/Kolkata — Planora's current target
deployment region — via ``planora_now`` in app.services.browser_reminders.
No per-user timezone architecture is introduced here.

Run from Railway Cron (NOT inside the uvicorn process)::

    python -m app.services.reminder_runner

The job opens its own DB session, runs once, closes the session, and
exits — exactly what Railway Cron expects. It is idempotent: re-runs
never duplicate a delivery, and one user's failure never stops the
remaining users. There is intentionally no infinite loop here.

Dev-only test push (verifies backend -> push service -> service worker ->
browser for one operator-owned account; never a production API)::

    python -m app.services.reminder_runner --send-test user@example.com
"""

import argparse
import logging
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models.user import User
from app.services.browser_reminders import (
    PAYLOADS,
    evaluate_missed_reminders,
    evaluate_planning_reminder,
    evaluate_reflection_reminder,
    get_push_subscription,
    planora_now,
    send_web_push,
)

logger = logging.getLogger(__name__)


def run_due_reminders(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Evaluate and send all due reminders for every user.

    Safe to run repeatedly (Railway Cron: */15 * * * *). `now` may be
    naive (Planora wall time), aware (converted to Asia/Kolkata), or None
    (current moment in Asia/Kolkata). Returns per-type send counts.
    """
    current = planora_now(now)
    totals = {"planning": 0, "missed_task": 0, "reflection": 0}
    users = db.query(User).all()
    for user in users:
        try:
            if evaluate_planning_reminder(db, user, current):
                totals["planning"] += 1
        except Exception:  # noqa: BLE001 - continue with other users/types
            logger.exception("Planning reminder failed for user %s", user.id)
        try:
            totals["missed_task"] += evaluate_missed_reminders(db, user)
        except Exception:  # noqa: BLE001
            logger.exception("Missed-task reminders failed for user %s", user.id)
        try:
            if evaluate_reflection_reminder(db, user, current):
                totals["reflection"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("Reflection reminder failed for user %s", user.id)
    return totals


def send_test_notification(db: Session, email: str, reminder_type: str = "planning") -> bool:
    """Send one test push to `email`'s existing subscription.

    Dev/operator use only: requires DB access, so it is never exposed as
    an HTTP endpoint. Sends directly without recording a ReminderDelivery,
    keeping test pushes out of production idempotency records.
    """
    if reminder_type not in PAYLOADS:
        print(f"Unknown reminder type: {reminder_type}", file=sys.stderr)
        return False
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print(f"No user found for {email}", file=sys.stderr)
        return False
    if get_push_subscription(db, user) is None:
        print(f"User {email} has no push subscription yet.", file=sys.stderr)
        return False
    sent = send_web_push(db, user, PAYLOADS[reminder_type])
    print("Test notification sent." if sent else "Test notification could not be sent.")
    return sent


def main(argv: list[str] | None = None) -> dict[str, int] | bool:
    parser = argparse.ArgumentParser(description="Planora browser-reminder cron job")
    parser.add_argument(
        "--send-test",
        metavar="EMAIL",
        default=None,
        help="Dev-only: send one test push to EMAIL's existing subscription and exit.",
    )
    parser.add_argument(
        "--type",
        default="planning",
        choices=sorted(PAYLOADS),
        help="Payload to use with --send-test (default: planning).",
    )
    args = parser.parse_args(argv)
    # Same idempotent table creation the API service performs at startup,
    # so the cron works even if it runs before the API on a fresh database.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if args.send_test:
            return send_test_notification(db, args.send_test, args.type)
        totals = run_due_reminders(db)
    finally:
        db.close()
    logger.info("Reminder run complete: %s", totals)
    return totals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = main()
    if isinstance(result, bool):
        sys.exit(0 if result else 1)
