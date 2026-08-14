import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


class RecommendationEndpointTests(unittest.TestCase):
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

    def test_recommend_returns_the_best_current_task(self):
        self.client.post(
            "/tasks",
            json={
                "title": "Future task",
                "duration_minutes": 30,
                "deadline": "2040-01-03T09:00:00",
                "priority": "high",
            },
        )
        self.client.post(
            "/tasks",
            json={
                "title": "Overdue task",
                "duration_minutes": 30,
                "deadline": "2039-12-31T09:00:00",
                "priority": "low",
            },
        )

        response = self.client.get("/recommend?current_time=2040-01-01T09:00:00")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["recommended_task"]["title"], "Overdue task")
        self.assertEqual(data["reason"], "Task is overdue.")


if __name__ == "__main__":
    unittest.main()
