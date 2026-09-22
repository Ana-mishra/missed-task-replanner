import unittest
from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.daily_reflection import DailyReflection
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
            user = db.query(User).filter(User.email == "tests@planora.local").first()
            if user is None:
                user = User(name="Endpoint Test User", email="tests@planora.local", password_hash="test")
                db.add(user)
                db.flush()
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
            db.add(TaskHistory(
                task_id=task.id,
                user_id=user.id,
                event_type="completed",
                timestamp=datetime(2026, 8, 11, 10),
            ))
            db.commit()

        response = self.client.get("/analytics/reflection/weekly?week_start=2026-08-10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["week_start"], "2026-08-10")
        self.assertEqual(response.json()["week_end"], "2026-08-16")
        self.assertEqual(response.json()["tasks_completed"], 1)
        self.assertEqual(response.json()["recovery_overview_missed"], 0)
        self.assertEqual(response.json()["recovery_overview_recovered"], 0)
        self.assertEqual(len(response.json()["daily_completed_tasks"]), 7)
        self.assertEqual(len(response.json()["daily_scheduled_completed_tasks"]), 7)

    def test_notes_returns_saved_notes_newest_first(self):
        with self.session_local() as db:
            user = db.query(User).filter(User.email == "tests@planora.local").first()
            if user is None:
                user = User(name="Endpoint Test User", email="tests@planora.local", password_hash="test")
                db.add(user)
                db.flush()
            db.add_all([
                DailyReflection(
                    user_id=user.id,
                    reflection_date=date(2026, 8, 20),
                    note_to_self="Older note",
                ),
                DailyReflection(
                    user_id=user.id,
                    reflection_date=date(2026, 8, 21),
                    note_to_self="Newer note",
                ),
                DailyReflection(
                    user_id=user.id,
                    reflection_date=date(2026, 8, 22),
                    note_to_self="",
                ),
            ])
            db.commit()

        response = self.client.get("/analytics/reflection/notes")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"date": "2026-08-21", "note": "Newer note"},
                {"date": "2026-08-20", "note": "Older note"},
            ],
        )

    def test_weekly_response_includes_plan_stability_task_titles(self):
        with self.session_local() as db:
            user = db.query(User).filter(User.email == "tests@planora.local").first()
            if user is None:
                user = User(name="Endpoint Test User", email="tests@planora.local", password_hash="test")
                db.add(user)
                db.flush()
            db.flush()
            task = Task(
                user_id=user.id,
                title="Learning French",
                duration_minutes=30,
                deadline=datetime(2026, 8, 20, 10),
                priority="high",
            )
            db.add(task)
            db.flush()
            task_id = task.id
            db.add(TaskHistory(
                task_id=task_id,
                user_id=user.id,
                event_type="scheduled",
                timestamp=datetime(2026, 8, 11, 9),
            ))
            db.add(TaskHistory(
                task_id=task_id,
                user_id=user.id,
                event_type="missed",
                timestamp=datetime(2026, 8, 11, 10),
            ))
            db.commit()

        body = self.client.get("/analytics/reflection/weekly?week_start=2026-08-10").json()

        self.assertEqual(body["plan_stability"]["missed"], 1)
        self.assertEqual(
            body["plan_stability_tasks"]["missed"],
            [{"id": task_id, "title": "Learning French"}],
        )
