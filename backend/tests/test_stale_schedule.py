"""Regression tests for the stale persisted-schedule fix.

Product rule under test: a persisted scheduled task remains valid until its
scheduled END time has passed. scheduled_end <= planning time means stale and
must be replanned; scheduled_end > planning time (even if already started)
may be preserved.
"""

import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.task_history import TaskHistory


DAY = datetime(2040, 1, 2)


class StaleScheduleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
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
        self.client.headers.update(
            self.register_and_login("stale-schedule@planora.local")
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email):
        password = "secure-pass-123"
        registration = self.client.post(
            "/auth/register",
            json={"name": "Stale Schedule", "email": email, "password": password},
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(self, title, duration_minutes=60):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "deadline": "2040-01-03T09:00:00",
                "priority": "high",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def persist_schedule(self, task_id, start, end):
        with self.session_local() as db:
            task = db.get(Task, task_id)
            task.scheduled_start = start
            task.scheduled_end = end
            task.schedule_needs_refresh = False
            task.schedule_refresh_reason = None
            db.commit()

    def open_missed_cycle(self, task_id):
        """Record an outstanding missed event without touching the schedule."""
        with self.session_local() as db:
            task = db.get(Task, task_id)
            db.add(
                TaskHistory(
                    task_id=task_id,
                    user_id=task.user_id,
                    event_type="missed",
                    task_title=task.title,
                )
            )
            db.commit()

    def plan(self, now, window_hours=4):
        response = self.client.post(
            "/plan",
            json={
                "available_start": now.isoformat(),
                "available_end": (now + timedelta(hours=window_hours)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_future_task_is_preserved(self):
        task = self.create_task("Future")
        self.persist_schedule(task["id"], DAY.replace(hour=14), DAY.replace(hour=15))
        schedule = self.plan(DAY.replace(hour=13, minute=30))["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertEqual(item["scheduled_start"], DAY.replace(hour=14).isoformat())
        self.assertEqual(item["scheduled_end"], DAY.replace(hour=15).isoformat())

    def test_partially_elapsed_task_is_preserved(self):
        task = self.create_task("Partially elapsed")
        self.persist_schedule(task["id"], DAY.replace(hour=13), DAY.replace(hour=14))
        schedule = self.plan(DAY.replace(hour=13, minute=58))["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertEqual(item["scheduled_start"], DAY.replace(hour=13).isoformat())
        self.assertEqual(item["scheduled_end"], DAY.replace(hour=14).isoformat())

    def test_exact_end_boundary_is_stale(self):
        task = self.create_task("Exact boundary")
        self.persist_schedule(task["id"], DAY.replace(hour=13), DAY.replace(hour=14))
        schedule = self.plan(DAY.replace(hour=14))["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertTrue(
            datetime.fromisoformat(item["scheduled_end"])
            > DAY.replace(hour=14),
            f"expired slot survived: {item}",
        )
        self.assertFalse(
            item["scheduled_start"] == DAY.replace(hour=13).isoformat()
            and item["scheduled_end"] == DAY.replace(hour=14).isoformat()
        )

    def test_fully_elapsed_task_is_replanned(self):
        task = self.create_task("Fully elapsed")
        self.persist_schedule(task["id"], DAY.replace(hour=13), DAY.replace(hour=14))
        schedule = self.plan(DAY.replace(hour=14, minute=1))["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertTrue(
            datetime.fromisoformat(item["scheduled_start"])
            >= DAY.replace(hour=14, minute=1),
            f"expired slot survived: {item}",
        )

    def test_multiple_completely_expired_tasks_are_replanned(self):
        first = self.create_task("Expired A", duration_minutes=30)
        second = self.create_task("Expired B", duration_minutes=30)
        self.persist_schedule(
            first["id"], DAY.replace(hour=12, minute=16), DAY.replace(hour=12, minute=46)
        )
        self.persist_schedule(
            second["id"], DAY.replace(hour=12, minute=46), DAY.replace(hour=13, minute=16)
        )
        now = DAY.replace(hour=15)
        schedule = self.plan(now)["schedule"]
        old_slots = {
            (DAY.replace(hour=12, minute=16).isoformat(), DAY.replace(hour=12, minute=46).isoformat()),
            (DAY.replace(hour=12, minute=46).isoformat(), DAY.replace(hour=13, minute=16).isoformat()),
        }
        for item in schedule:
            self.assertNotIn(
                (item["scheduled_start"], item["scheduled_end"]),
                old_slots,
                f"completely expired slot survived: {item}",
            )
            self.assertTrue(datetime.fromisoformat(item["scheduled_end"]) > now)

    def test_expired_slot_with_outstanding_miss_does_not_survive_early_return(self):
        task = self.create_task("Outstanding expired", duration_minutes=30)
        self.open_missed_cycle(task["id"])
        self.persist_schedule(
            task["id"], DAY.replace(hour=7), DAY.replace(hour=7, minute=30)
        )
        now = DAY.replace(hour=9)
        schedule = self.plan(now)["schedule"]
        for item in schedule:
            self.assertTrue(
                datetime.fromisoformat(item["scheduled_end"]) > now,
                f"expired outstanding slot survived early return: {item}",
            )
        with self.session_local() as db:
            missed_events = (
                db.query(TaskHistory)
                .filter(
                    TaskHistory.task_id == task["id"],
                    TaskHistory.event_type == "missed",
                )
                .count()
            )
        # The open missed cycle must not gain a duplicate missed event.
        self.assertEqual(missed_events, 1)

    def test_valid_persisted_schedule_keeps_idempotent_behavior(self):
        task = self.create_task("Stable future")
        self.persist_schedule(task["id"], DAY.replace(hour=14), DAY.replace(hour=15))
        now = DAY.replace(hour=13, minute=30)
        first = self.plan(now)["schedule"]
        second = self.plan(now)["schedule"]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
