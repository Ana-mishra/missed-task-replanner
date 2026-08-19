import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User


class ReflectionEndpointTests(unittest.TestCase):
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

    def test_week_start_query_returns_weekly_response(self):
        with self.session_local() as db:
            user = User(name="Reflection test user", email="reflection@planora.local", password_hash="test")
            db.add(user)
            db.flush()
            task = Task(
                user_id=user.id,
                title="Reflection task",
                duration_minutes=30,
                actual_duration_minutes=25,
                deadline=datetime(2026, 8, 20, 10),
                priority="medium",
                completed=True,
            )
            db.add(task)
            db.flush()
            db.add(TaskHistory(task_id=task.id, event_type="completed", timestamp=datetime(2026, 8, 11, 10)))
            db.commit()

        response = self.client.get("/analytics/reflection/weekly?week_start=2026-08-10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["week_start"], "2026-08-10")
        self.assertEqual(response.json()["week_end"], "2026-08-16")
        self.assertEqual(response.json()["tasks_completed"], 1)
        self.assertEqual(len(response.json()["daily_completed_tasks"]), 7)
