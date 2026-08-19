import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory


class TaskHistoryListApiTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.engine = engine

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_task(self, title):
        return self.client.post("/tasks", json={
            "title": title, "duration_minutes": 30,
            "deadline": "2040-01-01T10:00:00", "priority": "medium",
        }).json()

    def test_returns_existing_events_in_newest_first_order_with_task_titles(self):
        first = self.create_task("First task")
        second = self.create_task("Second task")
        base = datetime(2040, 1, 1, 9)
        with self.session_local() as db:
            db.add_all([
                TaskHistory(task_id=first["id"], event_type="completed", timestamp=base),
                TaskHistory(task_id=second["id"], event_type="missed", timestamp=base + timedelta(minutes=1)),
                TaskHistory(task_id=second["id"], event_type="replanned", timestamp=base + timedelta(minutes=2), scheduled_start=base + timedelta(days=1)),
            ])
            db.commit()

        response = self.client.get("/task-history")

        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertEqual([item["event_type"] for item in history[:3]], ["replanned", "missed", "completed"])
        self.assertEqual(history[0]["task_title"], "Second task")
        self.assertIsNotNone(history[0]["scheduled_start"])

    def test_failed_replan_has_no_false_replanned_event_and_edits_preserve_history(self):
        task = self.create_task("Original title")
        with self.session_local() as db:
            db.add(TaskHistory(task_id=task["id"], event_type="missed", timestamp=datetime(2040, 1, 1, 9)))
            db.commit()

        task["title"] = "Edited title"
        self.assertEqual(self.client.put(f"/tasks/{task['id']}", json=task).status_code, 200)
        history = self.client.get("/task-history").json()
        task_events = [event for event in history if event["task_id"] == task["id"]]

        self.assertIn("missed", [event["event_type"] for event in task_events])
        self.assertNotIn("replanned", [event["event_type"] for event in task_events])


if __name__ == "__main__":
    unittest.main()
