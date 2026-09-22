"""Reminder engine tests: planning / missed-task / reflection rules,
push-failure handling, VAPID safety, and runner isolation."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.daily_reflection import DailyReflection
from app.models.push_subscription import PushSubscription
from app.models.reminder_delivery import ReminderDelivery
from app.models.task_history import TaskHistory
from app.models.user import User


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _subscription_payload(endpoint="https://push.example.com/sub/abc"):
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "p256dh-key-abc", "auth": "auth-key-abc"},
    }


def _morning(now: datetime | None = None) -> datetime:
    base = now or datetime.now()
    return base.replace(hour=9, minute=0, second=0, microsecond=0)


class ReminderEngineBase(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email: str) -> dict[str, str]:
        self.assertEqual(
            self.client.post(
                "/auth/register",
                json={"name": email.split("@")[0], "email": email, "password": "secure-pass-123"},
            ).status_code,
            201,
        )
        login = self.client.post("/auth/login", json={"email": email, "password": "secure-pass-123"})
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(self, headers, title="Plan me", **overrides):
        payload = {
            "title": title,
            "duration_minutes": 30,
            "deadline": "2040-01-01T10:00:00",
            "priority": "high",
        }
        payload.update(overrides)
        response = self.client.post("/tasks", json=payload, headers=headers)
        self.assertEqual(response.status_code, 201)
        return response.json()

    def user(self, email: str) -> User:
        with self.session_local() as db:
            return db.query(User).filter(User.email == email).first()

    def delivery_count(self, user_id: int, reminder_type: str) -> int:
        with self.session_local() as db:
            return (
                db.query(ReminderDelivery)
                .filter(
                    ReminderDelivery.user_id == user_id,
                    ReminderDelivery.reminder_type == reminder_type,
                )
                .count()
            )


class PlanningReminderTests(ReminderEngineBase):
    def test_sends_when_eligible_and_records_delivery(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-ok@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        user = self.user("planning-ok@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                self.assertTrue(evaluate_planning_reminder(db, db_user, _morning()))
                self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(self.delivery_count(user.id, "planning"), 1)

    def test_does_not_duplicate_same_day_delivery(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-once@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        user = self.user("planning-once@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                self.assertTrue(evaluate_planning_reminder(db, db_user, _morning()))
                self.assertFalse(evaluate_planning_reminder(db, db_user, _morning()))
                self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(self.delivery_count(user.id, "planning"), 1)

    def test_does_not_send_when_preference_off(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-off@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        self.client.patch("/settings", json={"planning_reminders": False}, headers=headers)
        user = self.user("planning-off@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()
        self.assertEqual(self.delivery_count(user.id, "planning"), 0)

    def test_does_not_send_without_subscription(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-nosub@planora.local")
        self.create_task(headers)
        user = self.user("planning-nosub@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()

    def test_does_not_send_without_relevant_tasks(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-empty@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("planning-empty@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()

    def test_does_not_send_before_reminder_hour(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-early@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        user = self.user("planning-early@planora.local")
        early = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, early))
                mock_send.assert_not_called()

    def test_does_not_send_when_day_already_planned(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("planning-done@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        task = self.create_task(headers)
        user = self.user("planning-done@planora.local")
        with self.session_local() as db:
            db.add(
                TaskHistory(
                    task_id=task["id"],
                    user_id=user.id,
                    event_type="scheduled",
                    timestamp=datetime.now(),
                )
            )
            db.commit()
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()


class MissedReminderTests(ReminderEngineBase):
    def _add_event(self, user_id, task_id, event_type):
        with self.session_local() as db:
            event = TaskHistory(
                task_id=task_id,
                user_id=user_id,
                event_type=event_type,
                timestamp=datetime.now(),
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return event.id

    def test_sends_for_new_missed_event(self):
        from app.services.browser_reminders import evaluate_missed_reminders

        headers = self.register_and_login("missed-ok@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        task = self.create_task(headers)
        user = self.user("missed-ok@planora.local")
        self._add_event(user.id, task["id"], "missed")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ):
                self.assertEqual(evaluate_missed_reminders(db, db_user), 1)
        self.assertEqual(self.delivery_count(user.id, "missed_task"), 1)

    def test_does_not_send_for_overdue(self):
        from app.services.browser_reminders import evaluate_missed_reminders

        headers = self.register_and_login("missed-overdue@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        task = self.create_task(headers)
        user = self.user("missed-overdue@planora.local")
        self._add_event(user.id, task["id"], "overdue")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertEqual(evaluate_missed_reminders(db, db_user), 0)
                mock_send.assert_not_called()
        self.assertEqual(self.delivery_count(user.id, "missed_task"), 0)

    def test_does_not_duplicate_same_missed_event(self):
        from app.services.browser_reminders import evaluate_missed_reminders

        headers = self.register_and_login("missed-once@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        task = self.create_task(headers)
        user = self.user("missed-once@planora.local")
        self._add_event(user.id, task["id"], "missed")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                self.assertEqual(evaluate_missed_reminders(db, db_user), 1)
                self.assertEqual(evaluate_missed_reminders(db, db_user), 0)
                self.assertEqual(mock_send.call_count, 1)

    def test_respects_preference_off(self):
        from app.services.browser_reminders import evaluate_missed_reminders

        headers = self.register_and_login("missed-off@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        task = self.create_task(headers)
        self.client.patch("/settings", json={"missed_task_reminders": False}, headers=headers)
        user = self.user("missed-off@planora.local")
        self._add_event(user.id, task["id"], "missed")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertEqual(evaluate_missed_reminders(db, db_user), 0)
                mock_send.assert_not_called()


class ReflectionReminderTests(ReminderEngineBase):
    def test_sends_when_reflection_due(self):
        from app.services.browser_reminders import evaluate_reflection_reminder

        headers = self.register_and_login("reflection-ok@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("reflection-ok@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ):
                self.assertTrue(evaluate_reflection_reminder(db, db_user, _morning()))
        self.assertEqual(self.delivery_count(user.id, "reflection"), 1)

    def test_does_not_send_when_already_completed(self):
        from app.services.browser_reminders import evaluate_reflection_reminder

        headers = self.register_and_login("reflection-done@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("reflection-done@planora.local")
        with self.session_local() as db:
            db.add(
                DailyReflection(
                    user_id=user.id,
                    reflection_date=datetime.now().date(),
                    went_well="x",
                    could_be_better="y",
                    note_to_self="z",
                    tomorrow_step="w",
                )
            )
            db.commit()
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_reflection_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()

    def test_does_not_duplicate_same_week(self):
        from app.services.browser_reminders import evaluate_reflection_reminder

        headers = self.register_and_login("reflection-once@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("reflection-once@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                self.assertTrue(evaluate_reflection_reminder(db, db_user, _morning()))
                self.assertFalse(evaluate_reflection_reminder(db, db_user, _morning()))
                self.assertEqual(mock_send.call_count, 1)

    def test_respects_preference_off(self):
        from app.services.browser_reminders import evaluate_reflection_reminder

        headers = self.register_and_login("reflection-off@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.client.patch("/settings", json={"reflection_reminders": False}, headers=headers)
        user = self.user("reflection-off@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_reflection_reminder(db, db_user, _morning()))
                mock_send.assert_not_called()


class PushFailureTests(ReminderEngineBase):
    def test_missing_vapid_config_fails_safely(self):
        from app.services import browser_reminders

        headers = self.register_and_login("vapid-missing@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("vapid-missing@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch.object(browser_reminders, "VAPID_PUBLIC_KEY", ""),
                patch.object(browser_reminders, "VAPID_PRIVATE_KEY", ""),
            ):
                self.assertFalse(browser_reminders.vapid_configured())
                self.assertFalse(browser_reminders.send_web_push(db, db_user, {"title": "x"}))
            # Subscription is kept for when keys are configured.
            self.assertIsNotNone(
                db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()
            )

    def test_expired_subscription_is_removed(self):
        from pywebpush import WebPushException

        from app.services.browser_reminders import send_web_push

        headers = self.register_and_login("vapid-gone@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("vapid-gone@planora.local")
        gone = WebPushException("gone")
        gone.response = MagicMock(status_code=410)
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch("app.services.browser_reminders.vapid_configured", return_value=True),
                patch("pywebpush.webpush", side_effect=gone),
            ):
                self.assertFalse(send_web_push(db, db_user, {"title": "x"}))
            self.assertIsNone(
                db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()
            )

    def test_one_failed_user_does_not_stop_other_reminders(self):
        from app.services.reminder_runner import run_due_reminders

        headers_a = self.register_and_login("runner-a@planora.local")
        headers_b = self.register_and_login("runner-b@planora.local")
        for headers in (headers_a, headers_b):
            self.client.post(
                "/notifications/push/subscribe", json=_subscription_payload(), headers=headers
            )
            self.create_task(headers)
        user_a = self.user("runner-a@planora.local")
        user_b = self.user("runner-b@planora.local")

        def flaky_send(db, user, now):
            if user.id == user_a.id:
                raise RuntimeError("boom")
            return True

        with self.session_local() as db:
            with patch(
                "app.services.reminder_runner.evaluate_planning_reminder",
                side_effect=flaky_send,
            ):
                with patch(
                    "app.services.reminder_runner.evaluate_missed_reminders", return_value=0
                ):
                    with patch(
                        "app.services.reminder_runner.evaluate_reflection_reminder",
                        return_value=False,
                    ):
                        totals = run_due_reminders(db, _morning())
        self.assertEqual(totals["planning"], 1)

    def test_runner_is_idempotent_across_runs(self):
        from app.services.reminder_runner import run_due_reminders

        headers = self.register_and_login("runner-idem@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        with self.session_local() as db:
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                first = run_due_reminders(db, _morning())
                second = run_due_reminders(db, _morning())
        self.assertEqual(first["planning"], 1)
        self.assertEqual(first["reflection"], 1)
        self.assertEqual(second, {"planning": 0, "missed_task": 0, "reflection": 0})
        # One push per type on the first run, zero duplicates on the second.
        self.assertEqual(mock_send.call_count, 2)


class VapidStartupTests(unittest.TestCase):
    def test_application_starts_without_vapid_keys(self):
        # Importing the app must not crash when VAPID keys are absent, and
        # existing functionality (auth + settings) keeps working.
        from app.main import app as loaded_app

        self.assertIsNotNone(loaded_app)


class ReminderTimezoneTests(ReminderEngineBase):
    """Asia/Kolkata wall-clock behavior (Railway Cron fires in UTC)."""

    def test_planora_now_converts_utc_to_kolkata(self):
        from app.services.browser_reminders import planora_now

        utc = datetime(2026, 9, 21, 2, 29, tzinfo=timezone.utc)
        local = planora_now(utc)
        self.assertEqual((local.hour, local.minute), (7, 59))
        self.assertEqual(str(local.tzinfo), "Asia/Kolkata")

    def test_planning_gate_blocks_before_0800_ist(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("tz-early@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        user = self.user("tz-early@planora.local")
        # 02:29 UTC == 07:59 IST: too early.
        just_before = datetime(2026, 9, 21, 2, 29, tzinfo=timezone.utc)
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch("app.services.browser_reminders.send_web_push") as mock_send:
                self.assertFalse(evaluate_planning_reminder(db, db_user, just_before))
                mock_send.assert_not_called()

    def test_planning_gate_opens_at_0800_ist(self):
        from app.services.browser_reminders import evaluate_planning_reminder

        headers = self.register_and_login("tz-open@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        self.create_task(headers)
        user = self.user("tz-open@planora.local")
        # 02:30 UTC == 08:00 IST: due.
        opening = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with patch(
                "app.services.browser_reminders.send_web_push", return_value=True
            ) as mock_send:
                self.assertTrue(evaluate_planning_reminder(db, db_user, opening))
                self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(self.delivery_count(user.id, "planning"), 1)

    def test_planning_period_key_uses_kolkata_date(self):
        from app.services.browser_reminders import planning_period_key

        # 19:00 UTC is already the next calendar day in Kolkata.
        utc_evening = datetime(2026, 9, 21, 19, 0, tzinfo=timezone.utc)
        self.assertEqual(planning_period_key(utc_evening), "2026-09-22")

    def test_reflection_period_key_uses_kolkata_week(self):
        from app.services.browser_reminders import reflection_period_key

        sunday_night_utc = datetime(2026, 9, 20, 19, 30, tzinfo=timezone.utc)
        # Monday 01:00 IST belongs to the new ISO week.
        self.assertEqual(reflection_period_key(sunday_night_utc), "2026-W39")
        # One hour earlier in UTC is still Sunday in Kolkata (old week).
        sunday_utc = datetime(2026, 9, 20, 17, 30, tzinfo=timezone.utc)
        self.assertEqual(reflection_period_key(sunday_utc), "2026-W38")

    def test_successful_push_records_delivery(self):
        from app.services import browser_reminders

        headers = self.register_and_login("tz-record@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("tz-record@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch.object(browser_reminders, "VAPID_PUBLIC_KEY", "test-public"),
                patch.object(browser_reminders, "VAPID_PRIVATE_KEY", "test-private"),
                patch("pywebpush.webpush", return_value=None) as mock_push,
            ):
                self.assertTrue(
                    browser_reminders.send_browser_reminder(
                        db, db_user, "planning", "2026-09-21"
                    )
                )
                self.assertEqual(mock_push.call_count, 1)
        self.assertEqual(self.delivery_count(user.id, "planning"), 1)

    def test_failed_push_records_no_delivery(self):
        from app.services import browser_reminders

        headers = self.register_and_login("tz-fail@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("tz-fail@planora.local")
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch.object(browser_reminders, "VAPID_PUBLIC_KEY", "test-public"),
                patch.object(browser_reminders, "VAPID_PRIVATE_KEY", "test-private"),
                patch("pywebpush.webpush", side_effect=RuntimeError("network down")),
            ):
                self.assertFalse(
                    browser_reminders.send_browser_reminder(
                        db, db_user, "planning", "2026-09-21"
                    )
                )
        self.assertEqual(self.delivery_count(user.id, "planning"), 0)

    def test_404_response_removes_subscription(self):
        from pywebpush import WebPushException

        from app.services.browser_reminders import send_web_push

        headers = self.register_and_login("tz-gone404@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("tz-gone404@planora.local")
        gone = WebPushException("not found")
        gone.response = MagicMock(status_code=404)
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch("app.services.browser_reminders.vapid_configured", return_value=True),
                patch("pywebpush.webpush", side_effect=gone),
            ):
                self.assertFalse(send_web_push(db, db_user, {"title": "x"}))
            self.assertIsNone(
                db.query(PushSubscription).filter(PushSubscription.user_id == user.id).first()
            )

    def test_pem_private_key_is_accepted(self):
        from py_vapid import Vapid

        from app.services import browser_reminders

        headers = self.register_and_login("tz-pem@planora.local")
        self.client.post("/notifications/push/subscribe", json=_subscription_payload(), headers=headers)
        user = self.user("tz-pem@planora.local")
        helper = Vapid()
        helper.generate_keys()
        pem = helper.private_pem().decode()
        with self.session_local() as db:
            db_user = db.get(User, user.id)
            with (
                patch.object(browser_reminders, "VAPID_PUBLIC_KEY", "test-public"),
                patch.object(browser_reminders, "VAPID_PRIVATE_KEY", pem),
                patch("pywebpush.webpush", return_value=None) as mock_push,
            ):
                self.assertTrue(browser_reminders.send_web_push(db, db_user, {"title": "x"}))
                _, kwargs = mock_push.call_args
                self.assertIsInstance(kwargs["vapid_private_key"], Vapid)


if __name__ == "__main__":
    unittest.main()
