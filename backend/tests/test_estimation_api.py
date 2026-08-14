import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


class EstimationEndpointTests(unittest.TestCase):
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

    def test_estimation_endpoint_returns_expected_statistics(self):
        created = self.client.post(
            "/tasks",
            json={
                "title": "Completed analytics task",
                "duration_minutes": 30,
                "deadline": "2040-01-01T10:00:00",
                "priority": "medium",
            },
        ).json()
        created["completed"] = True
        created["actual_duration_minutes"] = 45
        self.client.put(f"/tasks/{created['id']}", json=created)

        response = self.client.get("/analytics/estimation")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["completed_tasks"], 1)
        self.assertEqual(response.json()["estimated_minutes"], 30)
        self.assertEqual(response.json()["actual_minutes"], 45)
        self.assertEqual(response.json()["tendency"], "underestimate")
