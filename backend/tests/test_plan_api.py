import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory
from app.services.planning import PlanningResult, ScheduledTask


class PlanEndpointTests(unittest.TestCase):
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

    def create_task(self, title, duration_minutes=30):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "deadline": "2040-01-01T10:00:00",
                "priority": "high",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_plan_returns_and_persists_generated_schedule(self):
        included_task = self.create_task("Included plan task")
        skipped_task = self.create_task("Skipped plan task")

        try:
            scheduled_task = ScheduledTask(
                task_id=included_task["id"],
                title=included_task["title"],
                scheduled_start=datetime(2040, 1, 1, 9, 0),
                scheduled_end=datetime(2040, 1, 1, 9, 30),
            )
            result = PlanningResult(
                schedule=[scheduled_task],
                is_overloaded=True,
                unscheduled_minutes=30,
                bad_day=True,
            )
            with patch(
                "app.api.planning.PlanningEngine.generate_schedule",
                return_value=result,
            ) as generate_schedule:
                response = self.client.post(
                    "/plan",
                    json={
                        "available_start": "2040-01-01T09:00:00",
                        "available_end": "2040-01-01T10:00:00",
                        "energy_level": "low",
                        "bad_day": True,
                    },
                )

            self.assertEqual(response.status_code, 200)
            schedule = response.json()["schedule"]
            self.assertEqual(len(schedule), 1)
            self.assertTrue(response.json()["is_overloaded"])
            self.assertEqual(response.json()["unscheduled_minutes"], 30)
            self.assertTrue(response.json()["bad_day"])
            planned_task = schedule[0]
            self.assertEqual(planned_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(planned_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertTrue(generate_schedule.called)
            self.assertEqual(generate_schedule.call_args.args[3], "low")
            self.assertTrue(generate_schedule.call_args.args[4])

            saved_task = self.client.get(f"/tasks/{included_task['id']}").json()
            skipped_task_after_plan = self.client.get(f"/tasks/{skipped_task['id']}").json()
            self.assertEqual(saved_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(saved_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertIsNone(skipped_task_after_plan["scheduled_start"])
            self.assertIsNone(skipped_task_after_plan["scheduled_end"])
            self.assertFalse(skipped_task_after_plan["completed"])
        finally:
            self.client.delete(f"/tasks/{included_task['id']}")
            self.client.delete(f"/tasks/{skipped_task['id']}")

    def test_plan_rejects_an_invalid_time_range(self):
        response = self.client.post(
            "/plan",
            json={
                "available_start": "2040-01-01T10:00:00",
                "available_end": "2040-01-01T09:00:00",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_repeating_an_unchanged_plan_preserves_persisted_times_and_history(self):
        task = self.create_task("Stable plan")
        first = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        plan_request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first) as generate_schedule:
            self.assertEqual(self.client.post("/plan", json=plan_request).status_code, 200)
            self.assertEqual(generate_schedule.call_count, 1)

        with self.session_local() as db:
            before_history_count = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"],
                TaskHistory.event_type == "rescheduled",
            ).count()

        shifted = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"], task["title"], datetime(2040, 1, 1, 10), datetime(2040, 1, 1, 10, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=shifted) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={
                    "available_start": "2040-01-01T09:15:00",
                    "available_end": "2040-01-01T11:00:00",
                },
            )
            self.assertEqual(generate_schedule.call_count, 0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"][0]["scheduled_start"], "2040-01-01T09:00:00")
        stored_task = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored_task["scheduled_start"], "2040-01-01T09:00:00")
        self.assertEqual(stored_task["scheduled_end"], "2040-01-01T09:30:00")
        with self.session_local() as db:
            after_history_count = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"],
                TaskHistory.event_type == "rescheduled",
            ).count()
        self.assertEqual(after_history_count, before_history_count)

    def test_an_unscheduled_new_task_allows_the_planner_to_update_the_plan(self):
        scheduled_task = self.create_task("Already planned")
        first = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"], scheduled_task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first):
            self.assertEqual(
                self.client.post(
                    "/plan",
                    json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
                ).status_code,
                200,
            )

        new_task = self.create_task("New task")
        updated = PlanningResult(
            schedule=[
                ScheduledTask(
                    new_task["id"], new_task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                ),
                ScheduledTask(
                    scheduled_task["id"], scheduled_task["title"], datetime(2040, 1, 1, 9, 30), datetime(2040, 1, 1, 10)
                ),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=updated) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)
        self.assertEqual(len(response.json()["schedule"]), 2)

    def test_planning_relevant_task_edit_invalidates_the_saved_plan(self):
        task = self.create_task("Edited task")
        initial = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        edited_task = self.client.get(f"/tasks/{task['id']}").json()
        edited_task["duration_minutes"] = 45
        self.assertEqual(self.client.put(f"/tasks/{task['id']}", json=edited_task).status_code, 200)

        updated = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 45))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=updated) as generate_schedule:
            response = self.client.post("/plan", json=request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)

    def test_overloaded_plan_is_idempotent_when_some_tasks_are_intentionally_unscheduled(self):
        scheduled_task = self.create_task("Fits today", duration_minutes=60)
        unscheduled_task = self.create_task("Later work", duration_minutes=195)
        first_plan = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"],
                    scheduled_task["title"],
                    datetime(2040, 1, 1, 9),
                    datetime(2040, 1, 1, 10),
                )
            ],
            is_overloaded=True,
            unscheduled_minutes=195,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first_plan) as generate_schedule:
            first_response = self.client.post("/plan", json=request)
            self.assertEqual(generate_schedule.call_count, 1)

        self.assertTrue(first_response.json()["is_overloaded"])
        self.assertEqual(
            self.client.get(f"/tasks/{unscheduled_task['id']}").json()["scheduled_start"],
            None,
        )
        with self.session_local() as db:
            history_before = db.query(TaskHistory).filter(
                TaskHistory.event_type == "rescheduled"
            ).count()

        shifted_plan = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"],
                    scheduled_task["title"],
                    datetime(2040, 1, 1, 9, 30),
                    datetime(2040, 1, 1, 10, 30),
                )
            ],
            is_overloaded=True,
            unscheduled_minutes=195,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=shifted_plan) as generate_schedule:
            second_response = self.client.post(
                "/plan",
                json={"available_start": "2040-01-01T09:20:00", "available_end": "2040-01-01T11:00:00"},
            )
            self.assertEqual(generate_schedule.call_count, 0)

        self.assertTrue(second_response.json()["is_overloaded"])
        self.assertEqual(second_response.json()["unscheduled_minutes"], 195)
        self.assertEqual(second_response.json()["schedule"][0]["scheduled_start"], "2040-01-01T09:00:00")
        with self.session_local() as db:
            history_after = db.query(TaskHistory).filter(
                TaskHistory.event_type == "rescheduled"
            ).count()
        self.assertEqual(history_after, history_before)


if __name__ == "__main__":
    unittest.main()
