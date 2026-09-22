import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.user_settings import UserSettings


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


class SettingsEndpointTests(unittest.TestCase):
    """Default-settings behavior using the shared deterministic test user."""

    def setUp(self):
        self.engine = _engine()
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

    def test_get_creates_and_returns_default_settings(self):
        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "theme": "light",
                "planning_reminders": True,
                "missed_task_reminders": True,
                "reflection_reminders": True,
            },
        )

    def test_get_is_idempotent_and_stores_one_row(self):
        self.client.get("/settings")
        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        with self.session_local() as db:
            self.assertEqual(db.query(UserSettings).count(), 1)

    def test_patch_can_change_theme(self):
        response = self.client.patch("/settings", json={"theme": "dark"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["theme"], "dark")

    def test_patch_can_disable_one_notification_preference(self):
        response = self.client.patch("/settings", json={"planning_reminders": False})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["planning_reminders"])
        self.assertTrue(body["missed_task_reminders"])
        self.assertTrue(body["reflection_reminders"])

    def test_patch_does_not_overwrite_unspecified_settings(self):
        self.client.patch("/settings", json={"theme": "dark"})

        response = self.client.patch("/settings", json={"reflection_reminders": False})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["theme"], "dark")
        self.assertTrue(body["planning_reminders"])
        self.assertTrue(body["missed_task_reminders"])
        self.assertFalse(body["reflection_reminders"])

    def test_patch_can_update_multiple_fields_together(self):
        response = self.client.patch(
            "/settings",
            json={"theme": "system", "reflection_reminders": False},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["theme"], "system")
        self.assertFalse(body["reflection_reminders"])
        self.assertTrue(body["planning_reminders"])
        self.assertTrue(body["missed_task_reminders"])

    def test_patch_rejects_invalid_theme(self):
        response = self.client.patch("/settings", json={"theme": "midnight"})

        self.assertEqual(response.status_code, 422)

    def test_patch_rejects_non_boolean_notification_values(self):
        response = self.client.patch("/settings", json={"planning_reminders": "sometimes"})

        self.assertEqual(response.status_code, 422)


class SettingsAuthBoundaryTests(unittest.TestCase):
    """Real-JWT boundaries: no token and cross-user isolation."""

    def setUp(self):
        self.engine = _engine()
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        # This suite deliberately uses the real bearer-token dependency.
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)
        self.user_a_headers = self.register_and_login("settings-a@planora.local")
        self.user_b_headers = self.register_and_login("settings-b@planora.local")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/auth/register",
            json={"name": email.split("@")[0], "email": email, "password": "secure-pass-123"},
        )
        self.assertEqual(response.status_code, 201)
        token = self.client.post(
            "/auth/login", json={"email": email, "password": "secure-pass-123"}
        )
        self.assertEqual(token.status_code, 200)
        return {"Authorization": f"Bearer {token.json()['access_token']}"}

    def test_unauthenticated_access_is_rejected(self):
        self.assertEqual(self.client.get("/settings").status_code, 401)
        self.assertEqual(
            self.client.patch("/settings", json={"theme": "dark"}).status_code, 401
        )

    def test_users_cannot_access_or_modify_each_others_settings(self):
        user_a = self.client.get("/settings", headers=self.user_a_headers)
        self.assertEqual(user_a.status_code, 200)
        self.assertEqual(user_a.json()["theme"], "light")

        update = self.client.patch(
            "/settings", json={"theme": "dark", "planning_reminders": False},
            headers=self.user_a_headers,
        )
        self.assertEqual(update.status_code, 200)

        user_b = self.client.get("/settings", headers=self.user_b_headers)
        self.assertEqual(user_b.status_code, 200)
        self.assertEqual(
            user_b.json(),
            {
                "theme": "light",
                "planning_reminders": True,
                "missed_task_reminders": True,
                "reflection_reminders": True,
            },
        )

        with self.session_local() as db:
            self.assertEqual(db.query(UserSettings).count(), 2)
