"""Event timestamps are unambiguous UTC instants end to end.

Regression coverage for the production bug where naive UTC/server-wall-clock
timestamps were serialized without timezone info, parsed by JavaScript as
local IST, and displayed 5h30 early (08:19 UTC shown as 8:19 am instead of
1:49 pm Asia/Kolkata).

Storage stays naive UTC wall-clock (no migration); the API boundary emits
explicit UTC (``...Z``). Schedule/deadline wall-clock semantics are untouched.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory
from app.services.planning import PlanningResult, ScheduledTask


def assert_utc_instant(test_case, value, expected_utc):
    """Assert a serialized timestamp carries tz info and equals the instant."""
    test_case.assertTrue(
        value.endswith("Z") or value.endswith("+00:00"),
        f"timestamp {value!r} carries no explicit UTC timezone",
    )
    test_case.assertEqual(datetime.fromisoformat(value), expected_utc)


class EventTimestampUtcTests(unittest.TestCase):
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
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_task(self, title):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": 30,
                "deadline": "2040-01-01T10:00:00",
                "priority": "medium",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_created_event_is_serialized_with_explicit_utc_timezone(self):
        task = self.create_task("UTC created")

        history = self.client.get("/task-history").json()
        created = next(
            event for event in history
            if event["task_id"] == task["id"] and event["event_type"] == "created"
        )
        parsed = datetime.fromisoformat(created["timestamp"])
        self.assertIsNotNone(parsed.tzinfo)
        self.assertTrue(
            created["timestamp"].endswith("Z") or created["timestamp"].endswith("+00:00")
        )

    def test_completed_event_and_completed_at_carry_utc_timezone(self):
        task = self.create_task("UTC completed")
        task["completed"] = True

        response = self.client.put(f"/tasks/{task['id']}", json=task)
        self.assertEqual(response.status_code, 200)

        assert_utc_instant(
            self,
            response.json()["completed_at"],
            datetime.fromisoformat(response.json()["completed_at"]),
        )
        history = self.client.get("/history?range=all").json()
        completed = next(
            event for event in history
            if event["task_id"] == task["id"] and event["event_type"] == "completed"
        )
        assert_utc_instant(
            self, completed["timestamp"], datetime.fromisoformat(completed["timestamp"])
        )
        self.assertEqual(completed["completed_at"], response.json()["completed_at"])

    def test_plan_my_day_events_share_the_exact_execution_instant(self):
        first = self.create_task("Plan A")
        second = self.create_task("Plan B")
        execution_instant = datetime(2026, 9, 26, 8, 19, 0, tzinfo=timezone.utc)
        result = PlanningResult(
            schedule=[
                ScheduledTask(
                    first["id"], first["title"],
                    datetime(2026, 9, 26, 14, 3), datetime(2026, 9, 26, 14, 33),
                ),
                ScheduledTask(
                    second["id"], second["title"],
                    datetime(2026, 9, 26, 14, 33), datetime(2026, 9, 26, 15, 3),
                ),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )

        with patch(
            "app.api.planning.utcnow_naive",
            return_value=execution_instant.replace(tzinfo=None),
        ):
            with patch(
                "app.api.planning.PlanningEngine.generate_schedule", return_value=result
            ):
                response = self.client.post(
                    "/plan",
                    json={
                        "available_start": "2026-09-26T14:00:00",
                        "available_end": "2026-09-26T18:00:00",
                        "timezone": "Asia/Kolkata",
                    },
                )
        self.assertEqual(response.status_code, 200)

        events = self.client.get("/history?range=all").json()
        self.assertEqual(len(events), 2)
        for event in events:
            assert_utc_instant(self, event["timestamp"], execution_instant)
        # Schedule wall-clock semantics are unchanged: still naive, still local.
        for event in events:
            self.assertFalse(event["new_start"].endswith("Z"))
            self.assertNotEqual(event["timestamp"], event["new_start"])

    def test_independent_events_at_different_instants_remain_distinct(self):
        task = self.create_task("Distinct instants")
        first = datetime(2026, 9, 26, 8, 12, 0)
        second = datetime(2026, 9, 26, 9, 48, 0)
        with self.session_local() as db:
            db.add_all([
                TaskHistory(task_id=task["id"], event_type="missed", timestamp=first),
                TaskHistory(task_id=task["id"], event_type="recovered", timestamp=second),
            ])
            db.commit()

        events = self.client.get("/history?range=all").json()
        by_type = {event["event_type"]: event["timestamp"] for event in events}
        assert_utc_instant(
            self, by_type["missed"], first.replace(tzinfo=timezone.utc)
        )
        assert_utc_instant(
            self, by_type["recovered"], second.replace(tzinfo=timezone.utc)
        )
        self.assertNotEqual(by_type["missed"], by_type["recovered"])

    def test_legacy_naive_timestamps_are_interpreted_as_utc(self):
        """Pre-fix rows hold UTC wall-clock with no tz; API must not shift them."""
        task = self.create_task("Legacy row")
        legacy_wall_clock = datetime(2026, 9, 26, 8, 19, 0)
        with self.session_local() as db:
            db.add(
                TaskHistory(
                    task_id=task["id"], event_type="scheduled",
                    timestamp=legacy_wall_clock,
                )
            )
            db.commit()

        events = self.client.get("/history?range=all").json()
        scheduled = next(
            event for event in events
            if event["task_id"] == task["id"] and event["event_type"] == "scheduled"
        )
        # Same wall-clock, now unambiguous UTC: 08:19Z == 1:49 PM Asia/Kolkata.
        self.assertEqual(scheduled["timestamp"], "2026-09-26T08:19:00Z")
        assert_utc_instant(
            self,
            scheduled["timestamp"],
            datetime(2026, 9, 26, 8, 19, tzinfo=timezone.utc),
        )

    def test_full_path_ist_evening_event_round_trip(self):
        """1:49 PM IST -> backend 08:19Z -> DB -> API JSON -> (frontend) 1:49 pm.

        The frontend leg (``2026-09-26T08:19:00Z`` -> ``1:49 pm`` in
        Asia/Kolkata) is asserted in ``historyFormat.test.mjs``; here the
        backend guarantees the unambiguous ``...Z`` payload it depends on.
        """
        task = self.create_task("Full path")
        instant_utc = datetime(2026, 9, 26, 8, 19, 0, tzinfo=timezone.utc)
        with self.session_local() as db:
            db.add(
                TaskHistory(
                    task_id=task["id"], event_type="scheduled",
                    timestamp=datetime(2026, 9, 26, 8, 19, 0),
                )
            )
            db.commit()

        scheduled = next(
            event for event in self.client.get("/history?range=all").json()
            if event["task_id"] == task["id"] and event["event_type"] == "scheduled"
        )
        self.assertEqual(scheduled["timestamp"], "2026-09-26T08:19:00Z")
        assert_utc_instant(self, scheduled["timestamp"], instant_utc)
        # Stored bytes are unchanged UTC wall-clock (no schedule reinterpretation).
        with self.session_local() as db:
            stored = (
                db.query(TaskHistory)
                .filter(
                    TaskHistory.task_id == task["id"],
                    TaskHistory.event_type == "scheduled",
                )
                .one()
            )
            self.assertEqual(stored.timestamp, instant_utc.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
