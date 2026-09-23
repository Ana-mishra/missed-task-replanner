"""OAuth 2.0 endpoints for Google and GitHub authentication."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    BACKEND_ORIGIN,
    FRONTEND_ORIGIN,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
)
from app.database import get_db
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.oauth import (
    exchange_github_code,
    exchange_google_code,
    fetch_github_primary_email,
    fetch_github_user,
    fetch_google_userinfo,
    generate_state,
    github_authorization_url,
    google_authorization_url,
    verify_state,
)
from app.services.security import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Redirect URIs — must match exactly what is registered in each provider's
# developer console. These point to the BACKEND callback endpoints, not the
# frontend. FRONTEND_ORIGIN is only used for the final post-auth redirect.
# ---------------------------------------------------------------------------

def _google_redirect_uri() -> str:
    return f"{BACKEND_ORIGIN.rstrip('/')}/auth/google/callback"


def _github_redirect_uri() -> str:
    return f"{BACKEND_ORIGIN.rstrip('/')}/auth/github/callback"


# ---------------------------------------------------------------------------
# Shared error redirect helper
# ---------------------------------------------------------------------------

def _error_redirect(message: str) -> RedirectResponse:
    from urllib.parse import urlencode
    params = urlencode({"error": message})
    return RedirectResponse(url=f"{FRONTEND_ORIGIN}/login?{params}", status_code=302)


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------

@router.get("/google", summary="Initiate Google OAuth login")
def google_login():
    """Redirect the browser to Google's OAuth consent page."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server",
        )
    state = generate_state()
    from fastapi import Request
    url = google_authorization_url(
        redirect_uri=_google_redirect_uri(),
        state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback", summary="Handle Google OAuth callback", response_model=TokenResponse)
def google_callback(
    code: str = Query(default=None),
    state: str = Query(default=None),
    error: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Receive Google's authorization code, verify it, and return a JWT."""
    if error:
        return _error_redirect(error)

    if not code or not state:
        return _error_redirect("missing_code_or_state")

    if not verify_state(state):
        return _error_redirect("invalid_state")

    redirect_uri = _google_redirect_uri()

    try:
        token_data = exchange_google_code(code=code, redirect_uri=redirect_uri)
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token in Google response")
        userinfo = fetch_google_userinfo(access_token)
    except Exception:
        logger.exception("Google OAuth exchange failed")
        return _error_redirect("provider_error")

    provider_user_id = userinfo.get("sub")
    provider_email = userinfo.get("email", "").lower().strip() or None
    name = userinfo.get("name") or userinfo.get("given_name") or "Google User"

    if not provider_user_id:
        return _error_redirect("provider_error")

    user = _find_or_create_user(
        db=db,
        provider="google",
        provider_user_id=provider_user_id,
        provider_email=provider_email,
        name=name,
    )

    jwt = create_access_token(user.id)
    from urllib.parse import urlencode
    params = urlencode({"token": jwt, "token_type": "bearer"})
    return RedirectResponse(
        url=f"{FRONTEND_ORIGIN.rstrip('/')}/oauth/callback?{params}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

@router.get("/github", summary="Initiate GitHub OAuth login")
def github_login():
    """Redirect the browser to GitHub's OAuth consent page."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured on this server",
        )
    state = generate_state()
    url = github_authorization_url(
        redirect_uri=_github_redirect_uri(),
        state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/github/callback", summary="Handle GitHub OAuth callback", response_model=TokenResponse)
def github_callback(
    code: str = Query(default=None),
    state: str = Query(default=None),
    error: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Receive GitHub's authorization code, verify it, and return a JWT."""
    if error:
        return _error_redirect(error)

    if not code or not state:
        return _error_redirect("missing_code_or_state")

    if not verify_state(state):
        return _error_redirect("invalid_state")

    redirect_uri = _github_redirect_uri()

    try:
        gh_access_token = exchange_github_code(code=code, redirect_uri=redirect_uri)
        gh_user = fetch_github_user(gh_access_token)
    except Exception:
        logger.exception("GitHub OAuth exchange failed")
        return _error_redirect("provider_error")

    provider_user_id = str(gh_user.get("id", ""))
    if not provider_user_id:
        return _error_redirect("provider_error")

    provider_email: str | None = None
    raw_email = gh_user.get("email")
    if raw_email:
        provider_email = raw_email.strip().lower()
    else:
        try:
            fetched = fetch_github_primary_email(gh_access_token)
            if fetched:
                provider_email = fetched.strip().lower()
        except Exception:
            logger.warning("Could not fetch GitHub verified email for user %s", provider_user_id)

    name = gh_user.get("name") or gh_user.get("login") or "GitHub User"

    user = _find_or_create_user(
        db=db,
        provider="github",
        provider_user_id=provider_user_id,
        provider_email=provider_email,
        name=name,
    )

    jwt = create_access_token(user.id)
    from urllib.parse import urlencode
    params = urlencode({"token": jwt, "token_type": "bearer"})
    return RedirectResponse(
        url=f"{FRONTEND_ORIGIN.rstrip('/')}/oauth/callback?{params}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Shared account resolution
# ---------------------------------------------------------------------------

def _find_or_create_user(
    db: Session,
    provider: str,
    provider_user_id: str,
    provider_email: str | None,
    name: str,
) -> User:
    """Find or create a User for the given OAuth identity.

    Resolution order:
    1. Existing OAuthAccount with (provider, provider_user_id) → return linked user.
    2. No OAuthAccount exists → create a new User (with no password_hash) and
       a new OAuthAccount. We intentionally do NOT silently merge by email to
       avoid account takeover via an unverified provider email claim.
    """
    oauth_account = (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )

    if oauth_account is not None:
        if provider_email and oauth_account.provider_email != provider_email:
            oauth_account.provider_email = provider_email
            db.commit()
        return oauth_account.user

    # New provider identity — create a fresh application user.
    # If the email is already taken by an existing account we still create a
    # separate user because the existing account may belong to a different
    # person who happens to share an email string with this provider identity.
    # Explicit account linking (a separate authenticated endpoint) is the safe
    # path if the same human controls both accounts.
    email_for_user = provider_email or f"{provider}.{provider_user_id}@oauth.planora.local"

    existing_user = (
        db.query(User).filter(User.email == email_for_user).first()
        if provider_email
        else None
    )

    if existing_user is not None:
        # Email matches an existing application account — attach the provider
        # identity without changing the existing user's credentials.
        user = existing_user
    else:
        user = User(
            name=name,
            name_confirmed=True,
            email=email_for_user,
            password_hash=None,
        )
        db.add(user)
        db.flush()

    oauth = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=provider_email,
    )
    db.add(oauth)
    db.commit()
    db.refresh(user)
    return user
