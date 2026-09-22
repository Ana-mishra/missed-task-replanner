import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.push_subscription import PushSubscription
from app.models.user_settings import UserSettings


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _subscription_payload(endpoint="https://push.example.com/sub/abc"):
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "p256dh-key-abc", "auth": "auth-key-abc"},
    }


class PushSubscriptionAuthTests(unittest.TestCase):
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
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_unauthenticated_access_is_rejected(self):
        self.assertEqual(
            self.client.post("/notifications/push/subscribe", json=_subscription_payload()).status_code,
            401,
        )
        self.assertEqual(self.client.delete("/notifications/push/subscribe").status_code, 401)
        self.assertEqual(self.client.get("/notifications/push/vapid-public-key").status_code, 401)

    def test_subscription_lifecycle_with_isolation(self):
        headers_a = self._register_and_login("push-a@planora.local")
        headers_b = self._register_and_login("push-b@planora.local")

        # Creation.
        created = self.client.post(
            "/notifications/push/subscribe", json=_subscription_payload(), headers=headers_a
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["endpoint"], "https://push.example.com/sub/abc")

        # Update/idempotency: same user, new endpoint -> still one row.
        updated = self.client.post(
            "/notifications/push/subscribe",
            json=_subscription_payload("https://push.example.com/sub/xyz"),
            headers=headers_a,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["endpoint"], "https://push.example.com/sub/xyz")
        with self.session_local() as db:
            self.assertEqual(
                db.query(PushSubscription).filter(PushSubscription.user_id == 1).count(), 1
            )

        # User isolation: user B has no subscription visible from A's actions.
        with self.session_local() as db:
            rows = db.query(PushSubscription).all()
            self.assertEqual(len(rows), 1)
            self.assertNotEqual(rows[0].endpoint, "other")

        # Deletion removes only the current user's subscription.
        deleted = self.client.delete("/notifications/push/subscribe", headers=headers_b)
        self.assertEqual(deleted.status_code, 204)
        with self.session_local() as db:
            self.assertEqual(db.query(PushSubscription).count(), 1)

        deleted = self.client.delete("/notifications/push/subscribe", headers=headers_a)
        self.assertEqual(deleted.status_code, 204)
        with self.session_local() as db:
            self.assertEqual(db.query(PushSubscription).count(), 0)

        # Deleting again is idempotent.
        deleted_again = self.client.delete("/notifications/push/subscribe", headers=headers_a)
        self.assertEqual(deleted_again.status_code, 204)

    def test_invalid_payload_is_rejected(self):
        headers = self._register_and_login("push-invalid@planora.local")
        response = self.client.post(
            "/notifications/push/subscribe", json={"endpoint": "only-endpoint"}, headers=headers
        )
        self.assertEqual(response.status_code, 422)

    def test_vapid_public_key_is_returned_when_configured(self):
        import app.api.notifications as notifications_api

        headers = self._register_and_login("push-vapid@planora.local")
        original = notifications_api.VAPID_PUBLIC_KEY
        notifications_api.VAPID_PUBLIC_KEY = "B-test-public-key-not-a-secret"
        try:
            response = self.client.get("/notifications/push/vapid-public-key", headers=headers)
        finally:
            notifications_api.VAPID_PUBLIC_KEY = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"public_key": "B-test-public-key-not-a-secret"})

    def test_vapid_public_key_is_null_when_unconfigured(self):
        import app.api.notifications as notifications_api

        headers = self._register_and_login("push-novapid@planora.local")
        original = notifications_api.VAPID_PUBLIC_KEY
        notifications_api.VAPID_PUBLIC_KEY = ""
        try:
            response = self.client.get("/notifications/push/vapid-public-key", headers=headers)
        finally:
            notifications_api.VAPID_PUBLIC_KEY = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"public_key": None})

    def _register_and_login(self, email: str) -> dict[str, str]:
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


class BrowserReminderEligibilityTests(unittest.TestCase):
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
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)
        self.headers = self._register_and_login("reminder@planora.local")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_preference_off_means_no_reminder_even_with_subscription(self):
        from app.models.user import User
        from app.services.browser_reminders import should_send_browser_reminder

        self.client.post(
            "/notifications/push/subscribe", json=_subscription_payload(), headers=self.headers
        )
        self.client.patch("/settings", json={"planning_reminders": False}, headers=self.headers)
        with self.session_local() as db:
            user = db.query(User).filter(User.email == "reminder@planora.local").first()
            self.assertFalse(should_send_browser_reminder(db, user, "planning"))
            self.assertTrue(should_send_browser_reminder(db, user, "missed_task"))

    def test_no_subscription_means_no_reminder(self):
        from app.models.user import User
        from app.services.browser_reminders import should_send_browser_reminder

        with self.session_local() as db:
            user = db.query(User).filter(User.email == "reminder@planora.local").first()
            db.query(UserSettings).filter(UserSettings.user_id == user.id).delete()
            db.commit()
            self.assertFalse(should_send_browser_reminder(db, user, "planning"))

    def _register_and_login(self, email: str) -> dict[str, str]:
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


if __name__ == "__main__":
    unittest.main()
