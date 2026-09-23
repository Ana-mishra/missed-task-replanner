"""Tests for environment-aware OAuth return origins and dev CORS origins."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.oauth import extract_return_origin, generate_state, verify_state


class ReturnOriginStateTests(unittest.TestCase):
    def test_state_without_origin_verifies_and_extracts_none(self):
        state = generate_state()
        self.assertTrue(verify_state(state))
        self.assertIsNone(extract_return_origin(state))

    def test_state_with_origin_round_trips(self):
        state = generate_state("http://localhost:5173")
        self.assertTrue(verify_state(state))
        self.assertEqual(extract_return_origin(state), "http://localhost:5173")

    def test_tampered_origin_state_fails(self):
        state = generate_state("http://localhost:5173")
        self.assertFalse(verify_state(state + "x"))
        self.assertIsNone(extract_return_origin(state + "x"))

    def test_garbage_state_extracts_none(self):
        self.assertIsNone(extract_return_origin("not-a-state-token"))
        self.assertIsNone(extract_return_origin(""))


class OAuthReturnOriginApiTests(unittest.TestCase):
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
        self.client = TestClient(app, follow_redirects=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def _login_location(self, provider, next_origin=None):
        url = f"/auth/{provider}"
        if next_origin is not None:
            from urllib.parse import quote
            url += f"?next={quote(next_origin, safe='')}"
        with patch("app.api.oauth.GOOGLE_CLIENT_ID", "test-client-id"), \
             patch("app.api.oauth.GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch("app.api.oauth.GITHUB_CLIENT_ID", "test-client-id"), \
             patch("app.api.oauth.GITHUB_CLIENT_SECRET", "test-secret"), \
             patch("app.services.oauth.GOOGLE_CLIENT_ID", "test-client-id"):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        return response.headers["location"]

    def _state_from_login(self, provider, next_origin=None):
        location = self._login_location(provider, next_origin)
        params = parse_qs(urlparse(location).query)
        return params["state"][0]

    def test_localhost_next_is_embedded_in_state(self):
        for provider in ("google", "github"):
            state = self._state_from_login(provider, "http://localhost:5173")
            self.assertTrue(verify_state(state))
            self.assertEqual(extract_return_origin(state), "http://localhost:5173")

    def test_disallowed_next_is_not_embedded(self):
        state = self._state_from_login("google", "https://evil.example.com")
        self.assertTrue(verify_state(state))
        self.assertIsNone(extract_return_origin(state))

    def test_callback_redirects_to_localhost_origin(self):
        state = generate_state("http://localhost:5173")
        fake_userinfo = {
            "sub": "uid-localhost-redirect",
            "email": "localhost@example.com",
            "email_verified": True,
            "name": "Localhost User",
        }
        with patch("app.api.oauth.exchange_google_code",
                    return_value={"access_token": "tok"}), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=x&state={state}")
        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        self.assertTrue(
            location.startswith("http://localhost:5173/oauth/callback"),
            f"expected localhost callback, got: {location}",
        )

    def test_callback_with_disallowed_origin_falls_back_to_frontend(self):
        state = generate_state("https://evil.example.com")
        fake_userinfo = {
            "sub": "uid-evil-fallback",
            "email": "evil@example.com",
            "email_verified": True,
            "name": "Evil User",
        }
        with patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.api.oauth.exchange_google_code",
                    return_value={"access_token": "tok"}), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=x&state={state}")
        location = response.headers["location"]
        self.assertIn("frontend.example.com", location)
        self.assertNotIn("evil.example.com", location)

    def test_legacy_state_without_origin_uses_frontend_origin(self):
        state = generate_state()
        fake_userinfo = {
            "sub": "uid-legacy-redirect",
            "email": "legacy@example.com",
            "email_verified": True,
            "name": "Legacy User",
        }
        with patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.api.oauth.exchange_google_code",
                    return_value={"access_token": "tok"}), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=x&state={state}")
        self.assertIn("frontend.example.com", response.headers["location"])


class CorsDevOriginTests(unittest.TestCase):
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

    def test_localhost_dev_origin_is_allowed(self):
        response = self.client.get(
            "/auth/me", headers={"Origin": "http://localhost:5173"}
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )

    def test_unlisted_origin_is_not_allowed(self):
        response = self.client.get(
            "/auth/me", headers={"Origin": "https://evil.example.com"}
        )
        self.assertNotEqual(
            response.headers.get("access-control-allow-origin"),
            "https://evil.example.com",
        )


if __name__ == "__main__":
    unittest.main()
