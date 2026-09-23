"""OAuth 2.0 helpers: state CSRF tokens, Google OIDC, GitHub token exchange."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import urllib.parse

import httpx

from app.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OAUTH_STATE_SECRET,
)

# ---------------------------------------------------------------------------
# CSRF state token (HMAC-signed, time-limited)
# ---------------------------------------------------------------------------

_STATE_TTL_SECONDS = 600


def generate_state() -> str:
    """Return a signed, time-stamped CSRF state token."""
    nonce = secrets.token_urlsafe(24)
    ts = str(int(time.time()))
    payload = f"{nonce}:{ts}"
    sig = _sign(payload)
    return f"{payload}:{sig}"


def verify_state(state: str) -> bool:
    """Return True when *state* has a valid signature and has not expired."""
    try:
        parts = state.rsplit(":", 1)
        if len(parts) != 2:
            return False
        payload, sig = parts
        if not hmac.compare_digest(sig, _sign(payload)):
            return False
        _, ts_str = payload.rsplit(":", 1)
        ts = int(ts_str)
        if abs(time.time() - ts) > _STATE_TTL_SECONDS:
            return False
        return True
    except Exception:
        return False


def _sign(payload: str) -> str:
    return hmac.new(
        OAUTH_STATE_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Google OIDC
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_authorization_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_google_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for Google token endpoint response."""
    with httpx.Client(timeout=10) as client:
        response = client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    response.raise_for_status()
    return response.json()


def fetch_google_userinfo(access_token: str) -> dict:
    """Return the verified user info from Google's userinfo endpoint."""
    with httpx.Client(timeout=10) as client:
        response = client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    if not data.get("email_verified"):
        raise ValueError("Google account email is not verified")
    return data


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

_GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def github_authorization_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{_GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_github_code(code: str, redirect_uri: str) -> str:
    """Exchange an authorization code for a GitHub access token."""
    with httpx.Client(timeout=10) as client:
        response = client.post(
            _GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise ValueError("GitHub did not return an access token")
    return token


def fetch_github_user(access_token: str) -> dict:
    """Return GitHub user profile."""
    with httpx.Client(timeout=10) as client:
        response = client.get(
            _GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
    response.raise_for_status()
    return response.json()


def fetch_github_primary_email(access_token: str) -> str | None:
    """Return the user's verified primary email from GitHub, or None."""
    with httpx.Client(timeout=10) as client:
        response = client.get(
            _GITHUB_EMAILS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
    if response.status_code != 200:
        return None
    emails = response.json()
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry.get("email")
    for entry in emails:
        if entry.get("verified"):
            return entry.get("email")
    return None
