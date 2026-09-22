"""API integration tests for GET /plant.

These tests exercise the full HTTP → DB path using an in-memory SQLite
database and the conftest.py autouse auth override, exactly following the
pattern of test_progress_api.py.
"""

import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


class PlantEndpointTests(unittest.TestCase):
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

    def _create_and_complete_task(self):
        """Helper: create a task and mark it completed via PUT."""
        created = self.client.post(
            "/tasks",
            json={
                "title": "Plant test task",
                "duration_minutes": 30,
                "deadline": "2040-01-20T10:00:00",
                "priority": "medium",
            },
        ).json()
        created["completed"] = True
        self.client.put(f"/tasks/{created['id']}", json=created)
        return created

    # -----------------------------------------------------------------------

    def test_plant_endpoint_returns_200(self):
        response = self.client.get("/plant")
        self.assertEqual(response.status_code, 200)

    def test_no_completed_tasks_returns_seed(self):
        response = self.client.get("/plant")
        data = response.json()
        self.assertEqual(data["growth_days"], 0)
        self.assertEqual(data["stage"], "seed")
        self.assertFalse(data["completed_today"])
        self.assertFalse(data["grew_today"])

    def test_response_has_all_required_fields(self):
        response = self.client.get("/plant")
        data = response.json()
        expected_keys = {
            "growth_days",
            "stage",
            "stage_progress",
            "current_streak_days",
            "days_since_last_growth",
            "completed_today",
            "grew_today",
            "vitality",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    def test_one_completed_task_produces_at_least_one_growth_day(self):
        self._create_and_complete_task()
        response = self.client.get("/plant")
        data = response.json()
        # Growth days >= 1 (today counts as a growth day)
        self.assertGreaterEqual(data["growth_days"], 1)
        self.assertIn(data["stage"], ["sprout", "young_plant", "growing", "flourishing", "mature"])

    def test_multiple_completions_same_day_not_double_counted(self):
        # Complete two tasks — should still be 1 Growth Day for today.
        self._create_and_complete_task()
        self._create_and_complete_task()
        response = self.client.get("/plant")
        data = response.json()
        # The number of growth_days should equal the number of distinct IST
        # calendar dates — since all completions happen "today" in the test
        # runner's timezone, growth_days must equal 1.
        self.assertEqual(data["growth_days"], 1)

    def test_non_completion_event_types_are_excluded(self):
        # POST a task but do NOT mark it completed.
        self.client.post(
            "/tasks",
            json={
                "title": "Incomplete task",
                "duration_minutes": 15,
                "deadline": "2040-01-20T10:00:00",
                "priority": "low",
            },
        )
        response = self.client.get("/plant")
        data = response.json()
        self.assertEqual(data["growth_days"], 0)
        self.assertEqual(data["stage"], "seed")

    def test_endpoint_requires_authentication(self):
        # Remove the auth override to test unauthenticated access.
        app.dependency_overrides.clear()

        # Re-inject only the DB override (not auth) so the request hits real
        # auth logic.
        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        client_no_auth = TestClient(app)
        response = client_no_auth.get("/plant")
        self.assertEqual(response.status_code, 401)

    def test_stage_progress_is_between_0_and_100(self):
        response = self.client.get("/plant")
        data = response.json()
        self.assertGreaterEqual(data["stage_progress"], 0.0)
        self.assertLessEqual(data["stage_progress"], 100.0)

    def test_vitality_is_valid_value(self):
        response = self.client.get("/plant")
        data = response.json()
        self.assertIn(data["vitality"], ["healthy", "waiting", "droopy", "very_droopy"])
