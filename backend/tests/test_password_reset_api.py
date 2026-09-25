import hashlib
import unittest
from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services import password_reset

NEUTRAL_MESSAGE = (
    "If an account exists for that email, we've sent you a password reset link."
)


class PasswordResetApiTests(unittest.TestCase):
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
        password_reset.clear_forgot_request_history()

    def tearDown(self):
        app.dependency_overrides.clear()
        password_reset.clear_forgot_request_history()
        self.engine.dispose()

    def register(self, email="ana@example.com", password="safe-password-123"):
        return self.client.post(
            "/auth/register",
            json={"name": "Ana", "email": email, "password": password},
        )

    def login(self, email="ana@example.com", password="safe-password-123"):
        return self.client.post(
            "/auth/login", json={"email": email, "password": password}
        )

    def token_rows(self):
        with self.session_local() as db:
            return db.query(PasswordResetToken).all()

    def issue_raw_token(self, email="ana@example.com"):
        """Mint a usable token through the service layer (as the email link
        would carry it), bypassing delivery."""
        with self.session_local() as db:
            user = db.query(User).filter(User.email == email).one()
            raw, digest = password_reset.generate_reset_token()
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=digest,
                    expires_at=password_reset.token_expiry(),
                )
            )
            db.commit()
            return raw

    def test_forgot_password_valid_email_creates_token_row(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.client.post(
            "/auth/forgot-password", json={"email": "ana@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        rows = self.token_rows()
        self.assertEqual(len(rows), 1)
        # Only the digest is persisted — never the raw token.
        self.assertEqual(len(rows[0].token_hash), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in rows[0].token_hash))
        self.assertGreater(rows[0].expires_at, password_reset.utcnow())
        self.assertIsNone(rows[0].used_at)

    def test_forgot_password_malformed_email_is_rejected(self):
        response = self.client.post(
            "/auth/forgot-password", json={"email": "not-an-email"}
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.token_rows(), [])

    def test_unknown_email_returns_same_neutral_response(self):
        response = self.client.post(
            "/auth/forgot-password", json={"email": "nobody@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        self.assertEqual(self.token_rows(), [])

    def test_reset_token_generation_is_unique_and_hashed(self):
        raw_one, digest_one = password_reset.generate_reset_token()
        raw_two, digest_two = password_reset.generate_reset_token()

        self.assertNotEqual(raw_one, raw_two)
        self.assertNotEqual(digest_one, digest_two)
        self.assertEqual(digest_one, hashlib.sha256(raw_one.encode()).hexdigest())

    def test_valid_token_resets_password(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()

        response = self.client.post(
            "/auth/reset-password",
            json={
                "token": raw,
                "password": "brand-new-password-456",
                "password_confirm": "brand-new-password-456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("successfully", response.json()["message"])

    def test_old_password_stops_working_and_new_password_works(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()
        reset = self.client.post(
            "/auth/reset-password",
            json={
                "token": raw,
                "password": "brand-new-password-456",
                "password_confirm": "brand-new-password-456",
            },
        )
        self.assertEqual(reset.status_code, 200)

        self.assertEqual(
            self.login(password="safe-password-123").status_code, 401
        )
        self.assertEqual(
            self.login(password="brand-new-password-456").status_code, 200
        )

    def test_expired_token_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()
        with self.session_local() as db:
            row = db.query(PasswordResetToken).one()
            row.expires_at = password_reset.utcnow() - timedelta(minutes=1)
            db.commit()

        response = self.client.post(
            "/auth/reset-password",
            json={
                "token": raw,
                "password": "brand-new-password-456",
                "password_confirm": "brand-new-password-456",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["detail"])

    def test_invalid_token_is_rejected(self):
        response = self.client.post(
            "/auth/reset-password",
            json={
                "token": "not-a-real-token",
                "password": "brand-new-password-456",
                "password_confirm": "brand-new-password-456",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid", response.json()["detail"].lower())

    def test_already_used_token_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()
        payload = {
            "token": raw,
            "password": "brand-new-password-456",
            "password_confirm": "brand-new-password-456",
        }
        self.assertEqual(self.client.post("/auth/reset-password", json=payload).status_code, 200)

        second = self.client.post("/auth/reset-password", json=payload)

        self.assertEqual(second.status_code, 400)
        self.assertIn("already been used", second.json()["detail"])

    def test_password_mismatch_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()

        response = self.client.post(
            "/auth/reset-password",
            json={
                "token": raw,
                "password": "brand-new-password-456",
                "password_confirm": "different-password-789",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_short_password_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        raw = self.issue_raw_token()

        response = self.client.post(
            "/auth/reset-password",
            json={"token": raw, "password": "short", "password_confirm": "short"},
        )

        self.assertEqual(response.status_code, 422)

    def test_resend_cooldown_suppresses_immediate_duplicates(self):
        self.assertEqual(self.register().status_code, 201)
        first = self.client.post(
            "/auth/forgot-password", json={"email": "ana@example.com"}
        )
        second = self.client.post(
            "/auth/forgot-password", json={"email": "ana@example.com"}
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["message"], NEUTRAL_MESSAGE)
        self.assertEqual(len(self.token_rows()), 1)

    def test_request_after_cooldown_rotates_token(self):
        self.assertEqual(self.register().status_code, 201)
        self.client.post("/auth/forgot-password", json={"email": "ana@example.com"})
        original_hash = self.token_rows()[0].token_hash

        with patch.object(password_reset, "RESEND_COOLDOWN_SECONDS", 0):
            response = self.client.post(
                "/auth/forgot-password", json={"email": "ana@example.com"}
            )

        self.assertEqual(response.status_code, 200)
        rows = self.token_rows()
        # Rotation keeps a single usable token; the digest changed.
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0].token_hash, original_hash)

    def test_oauth_only_user_is_unaffected(self):
        from app.models.oauth_account import OAuthAccount

        with self.session_local() as db:
            user = User(
                name="OAuth Only",
                email="oauthonly@example.com",
                password_hash=None,
                name_confirmed=True,
            )
            db.add(user)
            db.flush()
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="google",
                    provider_user_id="google-uid-oauth-only",
                    provider_email="oauthonly@example.com",
                )
            )
            db.commit()

        response = self.client.post(
            "/auth/forgot-password", json={"email": "oauthonly@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        self.assertEqual(self.token_rows(), [])
        with self.session_local() as db:
            unchanged = (
                db.query(User).filter(User.email == "oauthonly@example.com").one()
            )
            self.assertIsNone(unchanged.password_hash)

    def make_linked_user(self, email, provider, with_password=False):
        from app.models.oauth_account import OAuthAccount
        from app.services.security import hash_password

        with self.session_local() as db:
            user = User(
                name="Linked",
                email=email,
                password_hash=hash_password("local-password-123") if with_password else None,
                name_confirmed=True,
            )
            db.add(user)
            db.flush()
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=f"{provider}-uid-{email}",
                    provider_email=email,
                )
            )
            db.commit()

    def test_google_only_account_names_google_provider(self):
        self.make_linked_user("googler@example.com", "google")

        response = self.client.post(
            "/auth/forgot-password", json={"email": "googler@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        self.assertEqual(response.json()["provider"], "google")
        self.assertEqual(self.token_rows(), [])

    def test_github_only_account_names_github_provider(self):
        self.make_linked_user("ghubber@example.com", "github")

        response = self.client.post(
            "/auth/forgot-password", json={"email": "ghubber@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        self.assertEqual(response.json()["provider"], "github")
        self.assertEqual(self.token_rows(), [])

    def test_password_account_returns_no_provider(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.client.post(
            "/auth/forgot-password", json={"email": "ana@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["provider"])
        self.assertEqual(len(self.token_rows()), 1)

    def test_oauth_plus_password_account_uses_normal_reset_flow(self):
        self.make_linked_user("both@example.com", "google", with_password=True)

        response = self.client.post(
            "/auth/forgot-password", json={"email": "both@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["provider"])
        self.assertEqual(len(self.token_rows()), 1)

    def test_unknown_email_returns_no_provider(self):
        response = self.client.post(
            "/auth/forgot-password", json={"email": "nobody@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], NEUTRAL_MESSAGE)
        self.assertIsNone(response.json()["provider"])
        self.assertEqual(self.token_rows(), [])

    def test_reset_tokens_table_migration_is_idempotent(self):
        from app import database

        with self.session_local() as db:
            db.execute.__self__  # touch session; tables already exist
        # Fresh DB already has the table via create_all; the migration must
        # be a safe no-op there and on repeat runs.
        database.add_password_reset_tokens_table()
        database.add_password_reset_tokens_table()
        with self.session_local() as db:
            count = db.query(PasswordResetToken).count()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
