import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.user import User


class AuthenticationApiTests(unittest.TestCase):
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

    def register(self, email="ana@example.com", password="safe-password-123"):
        return self.client.post(
            "/auth/register",
            json={"name": "Ana", "email": email, "password": password},
        )

    def test_successful_registration_stores_a_password_hash(self):
        response = self.register(email=" ANA@Example.COM ")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": 1, "name": "Ana", "email": "ana@example.com"})
        with self.session_local() as db:
            user = db.query(User).one()
            self.assertNotEqual(user.password_hash, "safe-password-123")
            self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_duplicate_email_registration_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)

        duplicate = self.register(email="ANA@example.com")

        self.assertEqual(duplicate.status_code, 409)

    def test_successful_login_returns_a_bearer_access_token(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.client.post(
            "/auth/login",
            json={"email": "ana@example.com", "password": "safe-password-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertTrue(response.json()["access_token"])

    def test_incorrect_password_and_unknown_email_are_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        wrong_password = self.client.post(
            "/auth/login",
            json={"email": "ana@example.com", "password": "incorrect-password"},
        )
        unknown_email = self.client.post(
            "/auth/login",
            json={"email": "unknown@example.com", "password": "safe-password-123"},
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_email.status_code, 401)

    def test_valid_jwt_resolves_the_current_user(self):
        self.assertEqual(self.register().status_code, 201)
        token = self.client.post(
            "/auth/login",
            json={"email": "ana@example.com", "password": "safe-password-123"},
        ).json()["access_token"]

        with self.session_local() as db:
            user = get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db
            )

        self.assertEqual(user.email, "ana@example.com")

    def test_missing_or_invalid_token_is_rejected(self):
        with self.session_local() as db:
            with self.assertRaises(HTTPException) as missing_error:
                get_current_user(None, db)
            with self.assertRaises(HTTPException) as invalid_error:
                get_current_user(
                    HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt"), db
                )

        self.assertEqual(missing_error.exception.status_code, 401)
        self.assertEqual(invalid_error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
