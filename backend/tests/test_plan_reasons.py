"""Focused tests: /plan exposes deterministic planning reasons.

Covers the fresh planning path, the idempotent early-return path (which
reconstructs reasons without rescheduling), genuine replans after task
changes, and Bad Day behavior.
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
from app.models.task_history import TaskHistory


DAY = datetime(2040, 1, 2, 9, 0)


class PlanReasonTests(unittest.TestCase):
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
            self.register_and_login("plan-reasons@planora.local")
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email):
        password = "secure-pass-123"
        registration = self.client.post(
            "/auth/register",
            json={"name": "Plan Reasons", "email": email, "password": password},
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(self, title, deadline="2040-01-02T18:00:00", energy="medium"):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": 60,
                "deadline": deadline,
                "priority": "high",
                "energy_level": energy,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def plan(self, start=DAY, **overrides):
        payload = {
            "available_start": start.isoformat(),
            "available_end": (start + timedelta(hours=4)).isoformat(),
        }
        payload.update(overrides)
        response = self.client.post("/plan", json=payload)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def history_count(self):
        with self.session_local() as db:
            return db.query(TaskHistory).count()

    def test_fresh_plan_response_contains_deterministic_reason(self):
        task = self.create_task("Due today")
        schedule = self.plan()["schedule"]
        item = next(i for i in schedule if i["task_id"] == task["id"])
        self.assertEqual(item["reason"], "Kept because the deadline is today.")

    def test_idempotent_plan_returns_same_schedule_with_same_reason(self):
        task = self.create_task("Due today")
        first = self.plan()["schedule"]
        second = self.plan()["schedule"]
        self.assertEqual(first, second)
        item = next(i for i in second if i["task_id"] == task["id"])
        self.assertEqual(item["reason"], "Kept because the deadline is today.")

    def test_repeated_plan_creates_no_new_history(self):
        self.create_task("Due today")
        self.plan()
        before = self.history_count()
        self.plan()
        self.plan()
        self.assertEqual(self.history_count(), before)

    def test_idempotent_reason_matches_fresh_reason_after_clock_moves(self):
        task = self.create_task("Due today")
        first = self.plan()["schedule"]
        # Wall-clock time moves but the persisted slot is still active.
        second = self.plan(start=DAY + timedelta(minutes=20))["schedule"]
        first_item = next(i for i in first if i["task_id"] == task["id"])
        second_item = next(i for i in second if i["task_id"] == task["id"])
        self.assertEqual(
            (second_item["scheduled_start"], second_item["scheduled_end"]),
            (first_item["scheduled_start"], first_item["scheduled_end"]),
        )
        self.assertEqual(second_item["reason"], first_item["reason"])

    def test_added_task_replan_produces_fresh_reasons(self):
        first_task = self.create_task("First")
        first_schedule = self.plan()["schedule"]
        self.assertTrue(first_schedule)
        added = self.create_task("Added later")
        second_schedule = self.plan()["schedule"]
        by_id = {i["task_id"]: i for i in second_schedule}
        self.assertIn(added["id"], by_id)
        self.assertTrue(by_id[added["id"]]["reason"])
        self.assertTrue(by_id[first_task["id"]]["reason"])

    def test_bad_day_idempotent_plan_keeps_schedule_and_reason(self):
        task = self.create_task("Bad day due today", energy="low")
        first = self.plan(bad_day=True)["schedule"]
        second = self.plan(bad_day=True)["schedule"]
        self.assertEqual(first, second)
        item = next(i for i in second if i["task_id"] == task["id"])
        self.assertEqual(item["reason"], "Kept because the deadline is today.")


if __name__ == "__main__":
    unittest.main()
