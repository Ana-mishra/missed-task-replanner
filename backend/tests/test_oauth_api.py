"""Tests for Google and GitHub OAuth endpoints."""

import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services.oauth import generate_state, verify_state


class StateTokenTests(unittest.TestCase):
    def test_generated_state_verifies(self):
        state = generate_state()
        self.assertTrue(verify_state(state))

    def test_tampered_state_fails(self):
        state = generate_state()
        self.assertFalse(verify_state(state + "x"))

    def test_expired_state_fails(self):
        with patch("app.services.oauth.time.time", return_value=time.time() - 700):
            old_state = generate_state()
        self.assertFalse(verify_state(old_state))

    def test_garbage_state_fails(self):
        self.assertFalse(verify_state("not-a-state-token"))
        self.assertFalse(verify_state(""))


class OAuthApiTestBase(unittest.TestCase):
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


class GoogleOAuthTests(OAuthApiTestBase):
    def test_google_login_redirects_to_google(self):
        with patch("app.api.oauth.GOOGLE_CLIENT_ID", "test-client-id"), \
             patch("app.api.oauth.GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch("app.services.oauth.GOOGLE_CLIENT_ID", "test-client-id"):
            response = self.client.get("/auth/google")
        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        self.assertIn("accounts.google.com", location)
        self.assertIn("test-client-id", location)
        self.assertIn("state=", location)

    def test_google_authorization_url_uses_backend_origin(self):
        with patch("app.api.oauth.GOOGLE_CLIENT_ID", "test-client-id"), \
             patch("app.api.oauth.GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.services.oauth.GOOGLE_CLIENT_ID", "test-client-id"):
            response = self.client.get("/auth/google")
        location = response.headers["location"]
        from urllib.parse import urlparse, parse_qs, unquote
        params = parse_qs(urlparse(location).query)
        redirect_uri = params["redirect_uri"][0]
        self.assertTrue(
            redirect_uri.startswith("http://backend.example.com"),
            f"redirect_uri should start with BACKEND_ORIGIN, got: {redirect_uri}",
        )
        self.assertEqual(redirect_uri, "http://backend.example.com/auth/google/callback")

    def test_google_authorization_url_does_not_use_frontend_origin(self):
        with patch("app.api.oauth.GOOGLE_CLIENT_ID", "test-client-id"), \
             patch("app.api.oauth.GOOGLE_CLIENT_SECRET", "test-secret"), \
             patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.services.oauth.GOOGLE_CLIENT_ID", "test-client-id"):
            response = self.client.get("/auth/google")
        location = response.headers["location"]
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(location).query)
        redirect_uri = params["redirect_uri"][0]
        self.assertNotIn("frontend.example.com", redirect_uri)

    def test_google_token_exchange_uses_backend_redirect_uri(self):
        state = generate_state()
        fake_token_data = {"access_token": "tok"}
        fake_userinfo = {
            "sub": "uid-exchange-test",
            "email": "exchange@example.com",
            "email_verified": True,
            "name": "Exchange Test",
        }
        captured = {}
        def capturing_exchange(code, redirect_uri):
            captured["redirect_uri"] = redirect_uri
            return fake_token_data
        with patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.exchange_google_code", side_effect=capturing_exchange), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            self.client.get(f"/auth/google/callback?code=xcode&state={state}")
        self.assertEqual(
            captured.get("redirect_uri"),
            "http://backend.example.com/auth/google/callback",
        )

    def test_google_final_redirect_goes_to_frontend_not_backend(self):
        state = generate_state()
        fake_token_data = {"access_token": "tok"}
        fake_userinfo = {
            "sub": "uid-final-redirect",
            "email": "finalredirect@example.com",
            "email_verified": True,
            "name": "Final Redirect",
        }
        with patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.api.oauth.exchange_google_code", return_value=fake_token_data), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=xcode&state={state}")
        location = response.headers["location"]
        self.assertIn("frontend.example.com", location)
        self.assertIn("/oauth/callback", location)
        self.assertNotIn("backend.example.com", location)

    def test_google_login_returns_501_when_unconfigured(self):
        with patch("app.api.oauth.GOOGLE_CLIENT_ID", ""), \
             patch("app.api.oauth.GOOGLE_CLIENT_SECRET", ""):
            response = self.client.get("/auth/google")
        self.assertEqual(response.status_code, 501)

    def test_google_callback_missing_code_redirects_with_error(self):
        response = self.client.get("/auth/google/callback")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response.headers["location"])

    def test_google_callback_invalid_state_redirects_with_error(self):
        response = self.client.get("/auth/google/callback?code=abc&state=bad-state")
        self.assertEqual(response.status_code, 302)
        self.assertIn("invalid_state", response.headers["location"])

    def test_google_callback_provider_error_redirects(self):
        state = generate_state()
        with patch("app.api.oauth.exchange_google_code", side_effect=Exception("provider down")):
            response = self.client.get(f"/auth/google/callback?code=abc&state={state}")
        self.assertEqual(response.status_code, 302)
        self.assertIn("provider_error", response.headers["location"])

    def test_google_callback_creates_user_and_redirects_with_token(self):
        state = generate_state()
        fake_token_data = {"access_token": "fake-access-token"}
        fake_userinfo = {
            "sub": "google-uid-123",
            "email": "google@example.com",
            "email_verified": True,
            "name": "Google User",
        }
        with patch("app.api.oauth.exchange_google_code", return_value=fake_token_data), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=authcode&state={state}")

        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        self.assertIn("token=", location)
        self.assertIn("token_type=bearer", location)

        with self.session_local() as db:
            user = db.query(User).filter(User.email == "google@example.com").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.name, "Google User")
            self.assertIsNone(user.password_hash)
            oauth = db.query(OAuthAccount).filter(
                OAuthAccount.provider == "google",
                OAuthAccount.provider_user_id == "google-uid-123",
            ).first()
            self.assertIsNotNone(oauth)
            self.assertEqual(oauth.user_id, user.id)

    def test_google_callback_existing_oauth_account_logs_in(self):
        with self.session_local() as db:
            user = User(name="Existing", email="existing@example.com", password_hash=None, name_confirmed=True)
            db.add(user)
            db.flush()
            db.add(OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id="google-uid-existing",
                provider_email="existing@example.com",
            ))
            db.commit()

        state = generate_state()
        fake_token_data = {"access_token": "fake-access-token"}
        fake_userinfo = {
            "sub": "google-uid-existing",
            "email": "existing@example.com",
            "email_verified": True,
            "name": "Existing",
        }
        with patch("app.api.oauth.exchange_google_code", return_value=fake_token_data), \
             patch("app.api.oauth.fetch_google_userinfo", return_value=fake_userinfo):
            response = self.client.get(f"/auth/google/callback?code=authcode&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("token=", response.headers["location"])

        with self.session_local() as db:
            self.assertEqual(db.query(User).count(), 1)
            self.assertEqual(db.query(OAuthAccount).count(), 1)

    def test_google_callback_error_param_redirects(self):
        response = self.client.get("/auth/google/callback?error=access_denied")
        self.assertEqual(response.status_code, 302)
        self.assertIn("access_denied", response.headers["location"])


class GitHubOAuthTests(OAuthApiTestBase):
    def test_github_login_redirects_to_github(self):
        with patch("app.api.oauth.GITHUB_CLIENT_ID", "gh-client-id"), \
             patch("app.api.oauth.GITHUB_CLIENT_SECRET", "gh-secret"), \
             patch("app.services.oauth.GITHUB_CLIENT_ID", "gh-client-id"):
            response = self.client.get("/auth/github")
        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        self.assertIn("github.com", location)
        self.assertIn("gh-client-id", location)
        self.assertIn("state=", location)

    def test_github_authorization_url_uses_backend_origin(self):
        with patch("app.api.oauth.GITHUB_CLIENT_ID", "gh-client-id"), \
             patch("app.api.oauth.GITHUB_CLIENT_SECRET", "gh-secret"), \
             patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.services.oauth.GITHUB_CLIENT_ID", "gh-client-id"):
            response = self.client.get("/auth/github")
        location = response.headers["location"]
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(location).query)
        redirect_uri = params["redirect_uri"][0]
        self.assertEqual(redirect_uri, "http://backend.example.com/auth/github/callback")

    def test_github_authorization_url_does_not_use_frontend_origin(self):
        with patch("app.api.oauth.GITHUB_CLIENT_ID", "gh-client-id"), \
             patch("app.api.oauth.GITHUB_CLIENT_SECRET", "gh-secret"), \
             patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.services.oauth.GITHUB_CLIENT_ID", "gh-client-id"):
            response = self.client.get("/auth/github")
        location = response.headers["location"]
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(location).query)
        redirect_uri = params["redirect_uri"][0]
        self.assertNotIn("frontend.example.com", redirect_uri)

    def test_github_token_exchange_uses_backend_redirect_uri(self):
        state = generate_state()
        fake_gh_user = {"id": 55001, "login": "exchuser", "name": "Exch User", "email": "exch@example.com"}
        captured = {}
        def capturing_exchange(code, redirect_uri):
            captured["redirect_uri"] = redirect_uri
            return "gh-tok"
        with patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.exchange_github_code", side_effect=capturing_exchange), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user):
            self.client.get(f"/auth/github/callback?code=ghcode&state={state}")
        self.assertEqual(
            captured.get("redirect_uri"),
            "http://backend.example.com/auth/github/callback",
        )

    def test_github_final_redirect_goes_to_frontend_not_backend(self):
        state = generate_state()
        fake_gh_user = {"id": 55002, "login": "finaluser", "name": "Final User", "email": "ghfinal@example.com"}
        with patch("app.api.oauth.BACKEND_ORIGIN", "http://backend.example.com"), \
             patch("app.api.oauth.FRONTEND_ORIGIN", "http://frontend.example.com"), \
             patch("app.api.oauth.exchange_github_code", return_value="gh-tok"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")
        location = response.headers["location"]
        self.assertIn("frontend.example.com", location)
        self.assertIn("/oauth/callback", location)
        self.assertNotIn("backend.example.com", location)

    def test_github_login_returns_501_when_unconfigured(self):
        with patch("app.api.oauth.GITHUB_CLIENT_ID", ""), \
             patch("app.api.oauth.GITHUB_CLIENT_SECRET", ""):
            response = self.client.get("/auth/github")
        self.assertEqual(response.status_code, 501)

    def test_github_callback_missing_code_redirects_with_error(self):
        response = self.client.get("/auth/github/callback")
        self.assertEqual(response.status_code, 302)
        self.assertIn("error=", response.headers["location"])

    def test_github_callback_invalid_state_redirects_with_error(self):
        response = self.client.get("/auth/github/callback?code=abc&state=tampered")
        self.assertEqual(response.status_code, 302)
        self.assertIn("invalid_state", response.headers["location"])

    def test_github_callback_creates_user_with_email(self):
        state = generate_state()
        fake_gh_user = {"id": 99001, "login": "ghuser", "name": "GH User", "email": "ghuser@example.com"}
        with patch("app.api.oauth.exchange_github_code", return_value="gh-access-token"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("token=", response.headers["location"])

        with self.session_local() as db:
            user = db.query(User).filter(User.email == "ghuser@example.com").first()
            self.assertIsNotNone(user)
            self.assertIsNone(user.password_hash)
            oauth = db.query(OAuthAccount).filter(
                OAuthAccount.provider == "github",
                OAuthAccount.provider_user_id == "99001",
            ).first()
            self.assertIsNotNone(oauth)

    def test_github_callback_creates_user_without_public_email(self):
        state = generate_state()
        fake_gh_user = {"id": 99002, "login": "private_user", "name": None, "email": None}
        with patch("app.api.oauth.exchange_github_code", return_value="gh-token"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user), \
             patch("app.api.oauth.fetch_github_primary_email", return_value="private@example.com"):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("token=", response.headers["location"])

        with self.session_local() as db:
            oauth = db.query(OAuthAccount).filter(
                OAuthAccount.provider == "github",
                OAuthAccount.provider_user_id == "99002",
            ).first()
            self.assertIsNotNone(oauth)
            self.assertEqual(oauth.provider_email, "private@example.com")

    def test_github_callback_no_email_at_all_creates_synthetic_address(self):
        state = generate_state()
        fake_gh_user = {"id": 99003, "login": "anon_user", "name": "Anon", "email": None}
        with patch("app.api.oauth.exchange_github_code", return_value="gh-token"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user), \
             patch("app.api.oauth.fetch_github_primary_email", return_value=None):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("token=", response.headers["location"])

        with self.session_local() as db:
            user = db.query(User).filter(User.email.like("%99003%")).first()
            self.assertIsNotNone(user)

    def test_github_callback_existing_oauth_account_logs_in(self):
        with self.session_local() as db:
            user = User(name="GH Existing", email="ghexisting@example.com", password_hash=None, name_confirmed=True)
            db.add(user)
            db.flush()
            db.add(OAuthAccount(
                user_id=user.id,
                provider="github",
                provider_user_id="88000",
                provider_email="ghexisting@example.com",
            ))
            db.commit()

        state = generate_state()
        fake_gh_user = {"id": 88000, "login": "ghexisting", "name": "GH Existing", "email": "ghexisting@example.com"}
        with patch("app.api.oauth.exchange_github_code", return_value="gh-token"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("token=", response.headers["location"])

        with self.session_local() as db:
            self.assertEqual(db.query(User).count(), 1)
            self.assertEqual(db.query(OAuthAccount).count(), 1)

    def test_both_providers_link_to_same_user(self):
        with self.session_local() as db:
            user = User(name="Dual Auth", email="dual@example.com", password_hash=None, name_confirmed=True)
            db.add(user)
            db.flush()
            db.add(OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id="google-dual-uid",
                provider_email="dual@example.com",
            ))
            db.commit()
            user_id = user.id

        state = generate_state()
        fake_gh_user = {"id": 77001, "login": "dualuser", "name": "Dual Auth", "email": "dual@example.com"}
        with patch("app.api.oauth.exchange_github_code", return_value="gh-token"), \
             patch("app.api.oauth.fetch_github_user", return_value=fake_gh_user):
            response = self.client.get(f"/auth/github/callback?code=ghcode&state={state}")

        self.assertEqual(response.status_code, 302)

        with self.session_local() as db:
            self.assertEqual(db.query(User).count(), 1)
            self.assertEqual(db.query(OAuthAccount).count(), 2)
            github_oauth = db.query(OAuthAccount).filter(OAuthAccount.provider == "github").first()
            self.assertEqual(github_oauth.user_id, user_id)


if __name__ == "__main__":
    unittest.main()
