"""Startup mapper regression test for the Railway /auth/register crash.

Production failed with::

    sqlalchemy.exc.InvalidRequestError:
    Mapper 'Mapper[User(users)]' has no property 'settings'

The deployed revision registered ``UserSettings.user`` (with
``back_populates="settings"``) while ``User`` had no ``settings``
relationship. Imports succeeded, so the app booted; SQLAlchemy only
configures mappers lazily on first database use, so the crash surfaced
on the first ``POST /auth/register``.

These tests exercise the same ``uvicorn app.main:app`` import path and
prove both mappers configure successfully. They fail on any revision
where one side of the User <-> UserSettings relationship is missing.
"""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.user_settings import UserSettings


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


class StartupMapperConfigurationTests(unittest.TestCase):
    """Mirror the production startup path: import app.main, then use the DB."""

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
        # Registration is public; use the real auth dependency like prod.
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_user_settings_mappers_configure_successfully(self):
        # Same lazy configuration Railway hit on first database access.
        configure_mappers()
        user_mapper = User.__mapper__
        settings_mapper = UserSettings.__mapper__
        self.assertIn("settings", user_mapper.attrs)
        self.assertIn("user", settings_mapper.attrs)
        self.assertEqual(
            user_mapper.attrs["settings"].mapper.class_, UserSettings
        )
        self.assertEqual(settings_mapper.attrs["user"].mapper.class_, User)
        # One-to-one shape with delete cascade intact.
        self.assertFalse(user_mapper.attrs["settings"].uselist)
        self.assertIn("delete-orphan", user_mapper.attrs["settings"].cascade)

    def test_register_endpoint_configures_mappers_end_to_end(self):
        # The exact production trigger: first database use via registration.
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Mapper Check",
                "email": "mapper-check@planora.local",
                "password": "secure-pass-123",
            },
        )
        self.assertEqual(response.status_code, 201)


if __name__ == "__main__":
    unittest.main()
