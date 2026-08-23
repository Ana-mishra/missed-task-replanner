import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task
from app.models.user import User


class AnalyticsOwnershipEndpointTests(unittest.TestCase):
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

    def test_personalization_does_not_include_another_users_tasks(self):
        with self.session_local() as db:
            current_user = User(name="Current", email="tests@planora.local", password_hash="test")
            other_user = User(name="Other", email="other@planora.local", password_hash="test")
            db.add_all([current_user, other_user])
            db.flush()
            for index in range(3):
                db.add(Task(
                    user_id=other_user.id,
                    title=f"Other completed {index}",
                    duration_minutes=30,
                    actual_duration_minutes=45,
                    deadline=datetime(2040, 1, 1, 10),
                    priority="medium",
                    completed=True,
                    status="completed",
                    energy_level="medium",
                ))
            db.commit()

        response = self.client.get("/analytics/personalization")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"insights": []})


if __name__ == "__main__":
    unittest.main()