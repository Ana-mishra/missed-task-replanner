"""Shared authenticated principal for legacy endpoint tests.

The task API is now intentionally protected.  Existing endpoint tests focus
on task behavior rather than login, so they run as one deterministic test
account while the dedicated ownership tests exercise real JWT boundaries.
"""

import pytest
from fastapi import Depends

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def authenticated_test_user():
    def override_current_user(db=Depends(get_db)):
        user = db.query(User).filter(User.email == "tests@planora.local").first()
        if user is None:
            user = User(
                name="Endpoint Test User",
                email="tests@planora.local",
                password_hash="test-only-password-hash",
            )
            db.add(user)
            db.flush()
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
