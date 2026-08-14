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
from app.services.replanning import ReplanningResult


class TaskHistoryEndpointTests(unittest.TestCase):
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

    def history_for(self, task_id, event_type=None):
        with self.session_local() as db:
            query = db.query(TaskHistory).filter(TaskHistory.task_id == task_id)
            if event_type is not None:
                query = query.filter(TaskHistory.event_type == event_type)
            return query.all()

    def test_creating_task_records_created_event(self):
        task = self.create_task("Created task")

        events = self.history_for(task["id"], "created")

        self.assertEqual(len(events), 1)
        self.assertIsNotNone(events[0].timestamp)

    def test_planning_records_scheduled_only_for_scheduled_tasks(self):
        scheduled_task = self.create_task("Scheduled task")
        skipped_task = self.create_task("Skipped task")
        result = PlanningResult(
            schedule=[
                ScheduledTask(
                    task_id=scheduled_task["id"],
                    title=scheduled_task["title"],
                    scheduled_start=datetime(2040, 1, 1, 9, 0),
                    scheduled_end=datetime(2040, 1, 1, 9, 30),
                )
            ],
            is_overloaded=True,
            unscheduled_minutes=30,
        )

        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=result):
            response = self.client.post(
                "/plan",
                json={
                    "available_start": "2040-01-01T09:00:00",
                    "available_end": "2040-01-01T10:00:00",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.history_for(scheduled_task["id"], "scheduled")), 1)
        self.assertEqual(self.history_for(skipped_task["id"], "scheduled"), [])

    def test_replanning_records_missed_and_replanned_events(self):
        task = self.create_task("Missed task")
        result = ReplanningResult(
            schedule=[
                ScheduledTask(
                    task_id=task["id"],
                    title=task["title"],
                    scheduled_start=datetime(2040, 1, 1, 9, 0),
                    scheduled_end=datetime(2040, 1, 1, 9, 30),
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )

        with patch("app.api.replanning.ReplanningEngine.generate_revised_schedule", return_value=result):
            response = self.client.post(
                f"/replan/{task['id']}",
                json={
                    "available_start": "2040-01-01T09:00:00",
                    "available_end": "2040-01-01T10:00:00",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.history_for(task["id"], "missed")), 1)
        self.assertEqual(len(self.history_for(task["id"], "replanned")), 1)

    def test_completing_task_records_completed_event(self):
        task = self.create_task("Complete task")
        task["completed"] = True

        response = self.client.put(f"/tasks/{task['id']}", json=task)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.history_for(task["id"], "completed")), 1)

    def test_deleting_task_records_deleted_event(self):
        task = self.create_task("Delete task")

        response = self.client.delete(f"/tasks/{task['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(self.history_for(task["id"], "deleted")), 1)

    def test_get_requests_do_not_record_history(self):
        task = self.create_task("Read-only task")
        before_count = len(self.history_for(task["id"]))

        self.client.get("/tasks")
        self.client.get(f"/tasks/{task['id']}")
        self.client.get("/recommend?current_time=2040-01-01T09:00:00")

        self.assertEqual(len(self.history_for(task["id"])), before_count)


if __name__ == "__main__":
    unittest.main()
