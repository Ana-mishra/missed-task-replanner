import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory


class PostponementEndpointTests(unittest.TestCase):
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

    def create_task(self):
        response = self.client.post(
            "/tasks",
            json={
                "title": "Postponement task",
                "duration_minutes": 30,
                "deadline": "2040-01-01T10:00:00",
                "priority": "medium",
            },
        )
        return response.json()

    def add_cycle(self, task_id, offset):
        with self.session_local() as db:
            start = datetime(2040, 1, 1, 9, 0) + timedelta(minutes=offset)
            db.add_all(
                [
                    TaskHistory(task_id=task_id, event_type="missed", timestamp=start),
                    TaskHistory(task_id=task_id, event_type="replanned", timestamp=start + timedelta(minutes=1)),
                ]
            )
            db.commit()

    def test_endpoint_returns_analysis_and_custom_threshold(self):
        task = self.create_task()
        self.add_cycle(task["id"], 0)

        response = self.client.get(f"/tasks/{task['id']}/postponement?threshold=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["postponement_count"], 1)
        self.assertTrue(response.json()["needs_review"])

    def test_endpoint_rejects_invalid_threshold(self):
        task = self.create_task()

        response = self.client.get(f"/tasks/{task['id']}/postponement?threshold=0")

        self.assertEqual(response.status_code, 422)

    def test_endpoint_returns_not_found_for_unknown_task(self):
        response = self.client.get("/tasks/999999/postponement")

        self.assertEqual(response.status_code, 404)
