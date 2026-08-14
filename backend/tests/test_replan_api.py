import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.planning import ScheduledTask
from app.services.replanning import ReplanningResult


class ReplanEndpointTests(unittest.TestCase):
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

    def create_task(self, title, completed=False):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": 30,
                "deadline": "2040-01-01T10:00:00",
                "priority": "medium",
                "completed": completed,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def replan(self, task_id):
        return self.client.post(
            f"/replan/{task_id}",
            json={
                "available_start": "2040-01-01T09:00:00",
                "available_end": "2040-01-01T11:00:00",
            },
        )

    def test_replan_marks_task_missed_and_persists_revised_schedule(self):
        missed_task = self.create_task("Missed task")
        other_task = self.create_task("Other task")
        result = ReplanningResult(
            schedule=[
                ScheduledTask(
                    task_id=missed_task["id"],
                    title=missed_task["title"],
                    scheduled_start=datetime(2040, 1, 1, 9, 0),
                    scheduled_end=datetime(2040, 1, 1, 9, 30),
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )

        try:
            with patch(
                "app.api.replanning.ReplanningEngine.generate_revised_schedule",
                return_value=result,
            ):
                response = self.replan(missed_task["id"])

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["schedule"][0]["task_id"], missed_task["id"])
            self.assertFalse(response.json()["is_overloaded"])

            missed_after_replan = self.client.get(f"/tasks/{missed_task['id']}").json()
            other_after_replan = self.client.get(f"/tasks/{other_task['id']}").json()
            self.assertEqual(missed_after_replan["status"], "missed")
            self.assertFalse(missed_after_replan["completed"])
            self.assertEqual(missed_after_replan["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(missed_after_replan["scheduled_end"], "2040-01-01T09:30:00")
            self.assertIsNone(other_after_replan["scheduled_start"])
            self.assertIsNone(other_after_replan["scheduled_end"])
        finally:
            self.client.delete(f"/tasks/{missed_task['id']}")
            self.client.delete(f"/tasks/{other_task['id']}")

    def test_completed_task_cannot_be_replanned(self):
        task = self.create_task("Completed task", completed=True)
        try:
            response = self.replan(task["id"])
            self.assertEqual(response.status_code, 409)
        finally:
            self.client.delete(f"/tasks/{task['id']}")

    def test_nonexistent_task_returns_not_found(self):
        response = self.replan(999999)
        self.assertEqual(response.status_code, 404)

    def test_replan_rejects_invalid_time_window(self):
        task = self.create_task("Invalid window task")
        try:
            response = self.client.post(
                f"/replan/{task['id']}",
                json={
                    "available_start": "2040-01-01T11:00:00",
                    "available_end": "2040-01-01T09:00:00",
                },
            )
            self.assertEqual(response.status_code, 422)
        finally:
            self.client.delete(f"/tasks/{task['id']}")

    def test_replan_returns_overload_information(self):
        task = self.create_task("Overloaded task")
        result = ReplanningResult(schedule=[], is_overloaded=True, unscheduled_minutes=30)
        try:
            with patch(
                "app.api.replanning.ReplanningEngine.generate_revised_schedule",
                return_value=result,
            ):
                response = self.replan(task["id"])

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["is_overloaded"])
            self.assertEqual(response.json()["unscheduled_minutes"], 30)
        finally:
            self.client.delete(f"/tasks/{task['id']}")


if __name__ == "__main__":
    unittest.main()
