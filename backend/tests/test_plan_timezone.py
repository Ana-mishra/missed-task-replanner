"""Regression tests for the production timezone-frame bug.

The browser sends aware UTC timestamps and displays naive schedule walls as
local time. The backend must interpret the request in the browser-supplied
IANA timezone so staleness is evaluated in the same wall-clock frame the
user sees. Naive requests without a timezone keep the previous behavior.
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


TZ = "Asia/Kolkata"
# 2040-05-06 10:52 UTC == 16:22 Asia/Kolkata (IST has no DST).
NOW_UTC = "2040-05-06T10:52:00+00:00"
NOW_WALL = datetime(2040, 5, 6, 16, 22)


class PlanTimezoneTests(unittest.TestCase):
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
            self.register_and_login("plan-timezone@planora.local")
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email):
        password = "secure-pass-123"
        registration = self.client.post(
            "/auth/register",
            json={"name": "Plan Timezone", "email": email, "password": password},
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(self, title, duration_minutes=30):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "deadline": "2040-05-07T18:00:00",
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

    def plan(self, available_start, hours=4, **overrides):
        payload = {
            "available_start": available_start,
            "available_end": (
                datetime.fromisoformat(available_start) + timedelta(hours=hours)
            ).isoformat(),
            "timezone": TZ,
        }
        payload.update(overrides)
        response = self.client.post("/plan", json=payload)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_production_repro_expired_slots_are_replanned(self):
        first = self.create_task("Prod A")
        second = self.create_task("Prod B")
        self.persist_schedule(
            first["id"], datetime(2040, 5, 6, 14, 11), datetime(2040, 5, 6, 14, 41)
        )
        self.persist_schedule(
            second["id"], datetime(2040, 5, 6, 14, 41), datetime(2040, 5, 6, 15, 11)
        )
        schedule = self.plan(NOW_UTC)["schedule"]
        old_slots = {
            ("2040-05-06T14:11:00", "2040-05-06T14:41:00"),
            ("2040-05-06T14:41:00", "2040-05-06T15:11:00"),
        }
        self.assertTrue(schedule)
        for item in schedule:
            self.assertNotIn(
                (item["scheduled_start"], item["scheduled_end"]), old_slots
            )
            self.assertTrue(datetime.fromisoformat(item["scheduled_end"]) > NOW_WALL)
        with self.session_local() as db:
            missed = (
                db.query(TaskHistory)
                .filter(TaskHistory.event_type == "missed")
                .count()
            )
        self.assertEqual(missed, 2)

    def test_partially_elapsed_slot_is_preserved(self):
        task = self.create_task("Partial", duration_minutes=60)
        self.persist_schedule(
            task["id"], datetime(2040, 5, 6, 13, 0), datetime(2040, 5, 6, 14, 0)
        )
        # 08:28 UTC == 13:58 Asia/Kolkata.
        schedule = self.plan("2040-05-06T08:28:00+00:00")["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertEqual(item["scheduled_start"], "2040-05-06T13:00:00")
        self.assertEqual(item["scheduled_end"], "2040-05-06T14:00:00")

    def test_exact_end_boundary_is_stale(self):
        task = self.create_task("Boundary", duration_minutes=60)
        self.persist_schedule(
            task["id"], datetime(2040, 5, 6, 13, 0), datetime(2040, 5, 6, 14, 0)
        )
        # 08:30 UTC == 14:00 Asia/Kolkata.
        schedule = self.plan("2040-05-06T08:30:00+00:00")["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertFalse(
            item["scheduled_start"] == "2040-05-06T13:00:00"
            and item["scheduled_end"] == "2040-05-06T14:00:00"
        )
        self.assertTrue(
            datetime.fromisoformat(item["scheduled_start"])
            >= datetime(2040, 5, 6, 14, 0)
        )

    def test_future_slot_is_preserved(self):
        task = self.create_task("Future", duration_minutes=60)
        self.persist_schedule(
            task["id"], datetime(2040, 5, 6, 14, 0), datetime(2040, 5, 6, 15, 0)
        )
        # 08:00 UTC == 13:30 Asia/Kolkata.
        schedule = self.plan("2040-05-06T08:00:00+00:00")["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertEqual(item["scheduled_start"], "2040-05-06T14:00:00")
        self.assertEqual(item["scheduled_end"], "2040-05-06T15:00:00")

    def test_naive_request_without_timezone_keeps_previous_behavior(self):
        task = self.create_task("Naive future", duration_minutes=60)
        self.persist_schedule(
            task["id"], datetime(2040, 5, 6, 14, 0), datetime(2040, 5, 6, 15, 0)
        )
        response = self.client.post(
            "/plan",
            json={
                "available_start": "2040-05-06T13:30:00",
                "available_end": "2040-05-06T17:30:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        item = next(
            i for i in response.json()["schedule"] if i["task_id"] == task["id"]
        )
        self.assertEqual(item["scheduled_start"], "2040-05-06T14:00:00")
        self.assertEqual(item["scheduled_end"], "2040-05-06T15:00:00")

    def test_invalid_timezone_falls_back_safely(self):
        task = self.create_task("Bad tz", duration_minutes=60)
        self.persist_schedule(
            task["id"], datetime(2040, 5, 6, 14, 0), datetime(2040, 5, 6, 15, 0)
        )
        schedule = self.plan(NOW_UTC, timezone="Not/AZone")["schedule"]
        self.assertTrue(
            any(i["task_id"] == task["id"] for i in schedule)
        )


if __name__ == "__main__":
    unittest.main()
