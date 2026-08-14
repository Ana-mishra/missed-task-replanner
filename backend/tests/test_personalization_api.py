import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task import Task


class PersonalizationEndpointTests(unittest.TestCase):
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

    def test_endpoint_returns_a_structured_empty_result_when_no_data_exists(self):
        response = self.client.get("/analytics/personalization")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"insights": []})

    def test_endpoint_returns_estimation_insight(self):
        db = self.session_local()
        try:
            for index in range(1, 4):
                db.add(
                    Task(
                        title=f"Completed task {index}",
                        duration_minutes=30,
                        actual_duration_minutes=45,
                        deadline=datetime(2040, 1, 1, 10, 0),
                        priority="medium",
                        completed=True,
                        status="completed",
                        energy_level="medium",
                    )
                )
            db.commit()
        finally:
            db.close()

        response = self.client.get("/analytics/personalization")

        self.assertEqual(response.status_code, 200)
        insight = response.json()["insights"][0]
        self.assertEqual(insight["type"], "estimation")
        self.assertEqual(insight["evidence_count"], 3)
        self.assertEqual(insight["confidence"], "low")
