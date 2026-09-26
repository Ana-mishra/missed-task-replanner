import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.task_history import TaskHistory


class HistoryApiTests(unittest.TestCase):
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

    def add_event(self, task_id, event_type, timestamp, **kwargs):
        with self.session_local() as db:
            db.add(TaskHistory(task_id=task_id, event_type=event_type, timestamp=timestamp, **kwargs))
            db.commit()

    def test_history_returns_meaningful_events_with_schedule_change_details(self):
        task = self.create_task("Research")
        old_start = datetime(2026, 8, 18, 9)
        new_start = datetime(2026, 8, 19, 10)
        self.add_event(task["id"], "scheduled", old_start)
        self.add_event(
            task["id"],
            "rescheduled",
            new_start,
            old_start=old_start,
            old_end=old_start + timedelta(minutes=30),
            new_start=new_start,
            new_end=new_start + timedelta(minutes=30),
            reason="Schedule updated during replanning",
        )

        response = self.client.get("/history?range=all")

        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "rescheduled")
        self.assertEqual(events[0]["task_title"], "Research")
        self.assertEqual(events[0]["old_start"], old_start.isoformat())
        self.assertEqual(events[0]["new_start"], new_start.isoformat())
        self.assertIsNone(events[0]["reason"])
        self.assertEqual(events[1]["event_type"], "scheduled")

        summary = self.client.get("/history/summary?range=all").json()
        self.assertEqual(
            summary,
            {"completed": 0, "missed": 0, "recovered": 0, "rescheduled": 1},
        )

    def test_legacy_replanned_rows_are_excluded_from_the_new_user_facing_feed(self):
        task = self.create_task("Recover me")
        missed_at = datetime(2026, 8, 18, 9)
        self.add_event(task["id"], "missed", missed_at, reason="Task was not completed")
        self.add_event(
            task["id"],
            "replanned",
            missed_at + timedelta(hours=1),
            scheduled_start=datetime(2026, 8, 19, 9),
        )

        events = self.client.get("/history?range=all").json()

        self.assertEqual([event["event_type"] for event in events], ["missed"])

    def test_event_type_and_explicit_date_filters_apply_to_history_and_summary(self):
        task = self.create_task("Filtered task")
        self.add_event(task["id"], "completed", datetime(2026, 8, 1, 10))
        self.add_event(task["id"], "missed", datetime(2026, 8, 2, 10))
        self.add_event(task["id"], "recovered", datetime(2026, 8, 3, 10))
        self.add_event(task["id"], "rescheduled", datetime(2026, 9, 1, 10))

        response = self.client.get(
            "/history?event_type=missed&start_date=2026-08-01&end_date=2026-08-31"
        )
        summary = self.client.get(
            "/history/summary?start_date=2026-08-01&end_date=2026-08-31"
        )

        self.assertEqual([event["event_type"] for event in response.json()], ["missed"])
        self.assertEqual(
            summary.json(),
            {"completed": 1, "missed": 1, "recovered": 1, "rescheduled": 0},
        )

    def test_failed_replan_is_not_reported_as_recovered(self):
        task = self.create_task("Still missed")
        self.add_event(task["id"], "missed", datetime(2026, 8, 18, 9))

        events = self.client.get("/history?range=all").json()
        summary = self.client.get("/history/summary?range=all").json()

        self.assertEqual([event["event_type"] for event in events], ["missed"])
        self.assertEqual(summary["recovered"], 0)

    def test_missed_event_keeps_its_expired_slot_separate_from_the_deadline(self):
        task = self.create_task("Future deadline task")
        expired_start = datetime(2026, 9, 1, 15, 12)
        expired_end = expired_start + timedelta(minutes=30)
        future_deadline = datetime(2026, 9, 2, 17, 5)

        with self.session_local() as db:
            stored_task = db.get(Task, task["id"])
            stored_task.deadline = future_deadline
            db.add(
                TaskHistory(
                    task_id=task["id"],
                    event_type="missed",
                    timestamp=expired_end,
                    scheduled_start=expired_start,
                    scheduled_end=expired_end,
                    old_start=expired_start,
                    old_end=expired_end,
                    reason="Scheduled opportunity passed",
                )
            )
            recovered_start = datetime(2026, 9, 1, 18, 0)
            db.add(
                TaskHistory(
                    task_id=task["id"],
                    event_type="recovered",
                    timestamp=recovered_start,
                    new_start=recovered_start,
                    new_end=recovered_start + timedelta(minutes=30),
                    reason="Missed task was included in Plan My Day",
                )
            )
            db.commit()

        events = self.client.get("/history?range=all").json()
        event = next(event for event in events if event["event_type"] == "missed")

        self.assertEqual(event["event_type"], "missed")
        self.assertEqual(event["old_start"], expired_start.isoformat())
        self.assertEqual(event["old_end"], expired_end.isoformat())
        self.assertEqual(event["deadline"], future_deadline.isoformat())

    def test_named_range_summary_counts_rescheduled_events(self):
        task = self.create_task("Range summary")
        now = datetime.now().replace(microsecond=0)
        self.add_event(task["id"], "rescheduled", now)
        self.add_event(task["id"], "rescheduled", datetime(now.year - 1, 1, 1, 9))

        week_summary = self.client.get("/history/summary?range=week")
        all_summary = self.client.get("/history/summary?range=all")

        self.assertEqual(week_summary.status_code, 200)
        self.assertEqual(week_summary.json()["rescheduled"], 1)
        self.assertEqual(all_summary.json()["rescheduled"], 2)

    def test_history_excludes_no_op_reschedules_and_groups_one_plan_reshape(self):
        first = self.create_task("First moved task")
        second = self.create_task("Second moved task")
        third = self.create_task("No-op task")
        timestamp = datetime(2026, 8, 19, 10, 15)

        for task in (first, second):
            self.add_event(
                task["id"],
                "rescheduled",
                timestamp,
                old_start=datetime(2026, 8, 19, 9),
                old_end=datetime(2026, 8, 19, 9, 30),
                new_start=datetime(2026, 8, 19, 10),
                new_end=datetime(2026, 8, 19, 10, 30),
                reason="Plan reshaped",
            )
        same_start = datetime(2026, 8, 19, 11)
        self.add_event(
            third["id"], "rescheduled", timestamp,
            old_start=same_start, old_end=same_start + timedelta(minutes=30),
            new_start=same_start, new_end=same_start + timedelta(minutes=30),
            reason="Plan reshaped",
        )

        events = self.client.get("/history?range=all").json()
        summary = self.client.get("/history/summary?range=all").json()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "rescheduled")
        self.assertEqual(events[0]["task_title"], "Plan reshaped")
        self.assertEqual(events[0]["task_count"], 2)
        self.assertEqual(events[0]["reason"], "2 tasks were rearranged to fit your day.")
        self.assertEqual(summary["rescheduled"], 1)

    def test_history_events_at_different_actual_times_return_distinct_timestamps(self):
        task1 = self.create_task("First task")
        task2 = self.create_task("Second task")

        event_time_1 = datetime(2026, 9, 25, 13, 42, 0)
        event_time_2 = datetime(2026, 9, 25, 15, 18, 0)

        self.add_event(task1["id"], "completed", event_time_1, completed_at=event_time_1)
        self.add_event(
            task2["id"],
            "rescheduled",
            event_time_2,
            old_start=datetime(2026, 9, 25, 10, 0),
            old_end=datetime(2026, 9, 25, 10, 30),
            new_start=datetime(2026, 9, 25, 16, 0),
            new_end=datetime(2026, 9, 25, 16, 30),
            reason="Rescheduled task",
        )

        response = self.client.get("/history?range=all")
        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual(len(events), 2)

        # Returned newest first
        rescheduled_event = next(e for e in events if e["event_type"] == "rescheduled")
        completed_event = next(e for e in events if e["event_type"] == "completed")

        self.assertEqual(rescheduled_event["timestamp"], event_time_2.isoformat())
        self.assertEqual(completed_event["timestamp"], event_time_1.isoformat())
        self.assertNotEqual(rescheduled_event["timestamp"], completed_event["timestamp"])


if __name__ == "__main__":
    unittest.main()
