"""Focused tests: ordinary missed tasks recover through Plan My Day alone.

Product contract: the user must never need a manual "Recover" action.
A missed slot is detected by POST /plan, the task is automatically
considered in the same planning run, receives a new schedule when the
existing capacity/deadline rules allow, and records exactly one missed
event and one recovered event. Repeating Plan My Day creates nothing new.
No call to POST /replan/* is involved at any point.
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


class AutoRecoveryTests(unittest.TestCase):
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
            self.register_and_login("auto-recovery@planora.local")
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email):
        password = "secure-pass-123"
        registration = self.client.post(
            "/auth/register",
            json={"name": "Auto Recovery", "email": email, "password": password},
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(self, title):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": 30,
                "deadline": "2040-01-03T12:00:00",
                "priority": "high",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def history_event_count(self, task_id, event_type):
        from app.models.task_history import TaskHistory

        with self.session_local() as db:
            return (
                db.query(TaskHistory)
                .filter(
                    TaskHistory.task_id == task_id,
                    TaskHistory.event_type == event_type,
                )
                .count()
            )

    def test_missed_task_recovers_through_plan_my_day_alone(self):
        task = self.create_task("Will be missed")
        requested_start = datetime(2040, 1, 2, 9, 0)
        requested_end = requested_start + timedelta(hours=2)

        # Give the task a fully elapsed persisted slot (the missed state).
        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = requested_start - timedelta(hours=2)
            stored.scheduled_end = requested_start - timedelta(hours=1, minutes=30)
            stored.schedule_needs_refresh = False
            db.commit()

        def plan():
            response = self.client.post(
                "/plan",
                json={
                    "available_start": requested_start.isoformat(),
                    "available_end": requested_end.isoformat(),
                },
            )
            self.assertEqual(response.status_code, 200)
            return response.json()

        # First Plan My Day: automatically considered, rescheduled, recovered.
        first = plan()
        scheduled = {item["task_id"]: item for item in first["schedule"]}
        self.assertIn(task["id"], scheduled)
        self.assertGreaterEqual(
            datetime.fromisoformat(scheduled[task["id"]]["scheduled_start"]),
            requested_start,
        )
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)
        self.assertEqual(
            self.client.get(f"/tasks/{task['id']}").json()["status"], "pending"
        )

        # Second Plan My Day: same schedule, no duplicate history.
        second = plan()
        self.assertEqual(second["schedule"], first["schedule"])
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)


    def test_remissed_task_keeps_historical_flag_but_loses_slot(self):
        # A recovered slot can itself elapse. The historical "recovered"
        # flag must persist (History stays truthful) while the live task
        # returns to missed + unscheduled — the UI must gate its "currently
        # recovered" representation on the live slot, not on this flag.
        task = self.create_task("Recovered then missed again")
        first_start = datetime(2040, 1, 2, 9, 0)
        first_end = first_start + timedelta(hours=2)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = first_start - timedelta(hours=2)
            stored.scheduled_end = first_start - timedelta(hours=1, minutes=30)
            stored.schedule_needs_refresh = False
            db.commit()

        first_plan = self.client.post(
            "/plan",
            json={
                "available_start": first_start.isoformat(),
                "available_end": first_end.isoformat(),
            },
        )
        self.assertEqual(first_plan.status_code, 200)
        new_start = datetime.fromisoformat(
            next(
                item
                for item in first_plan.json()["schedule"]
                if item["task_id"] == task["id"]
            )["scheduled_start"]
        )

        # Plan again after the recovered slot has fully elapsed, with a
        # window too small to fit the 30-minute task, so it genuinely
        # remains missed and unscheduled.
        later_start = new_start + timedelta(hours=2)
        second_plan = self.client.post(
            "/plan",
            json={
                "available_start": later_start.isoformat(),
                "available_end": (later_start + timedelta(minutes=5)).isoformat(),
            },
        )
        self.assertEqual(second_plan.status_code, 200)

        live = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(live["status"], "missed")
        self.assertIsNone(live["scheduled_start"])
        self.assertIsNone(live["scheduled_end"])
        # Historical recovery is still recorded — and must not be mistaken
        # for a current recovery by display logic.
        self.assertTrue(live["was_replanned"])
        self.assertEqual(self.history_event_count(task["id"], "missed"), 2)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)


if __name__ == "__main__":
    unittest.main()
