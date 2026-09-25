"""Password-reset token issuance, delivery, and resend-cooldown helpers.

Tokens are 256-bit secrets (`secrets.token_urlsafe`) whose SHA-256 digest
alone is persisted — the raw value exists only inside the emailed link.
Email delivery uses any operator-configured SMTP relay (stdlib only) and
is best-effort: sending never fails a reset request, and failures are
logged without personal data. Raw tokens and passwords are never logged.
"""

import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from app import config

logger = logging.getLogger(__name__)

RESET_TOKEN_BYTES = 32
RESEND_COOLDOWN_SECONDS = config.PASSWORD_RESET_COOLDOWN_SECONDS
RESET_TOKEN_EXPIRE_MINUTES = config.PASSWORD_RESET_EXPIRE_MINUTES

# Last forgot-password request per normalized email. Only timestamps are
# kept (never tokens), purely to pace resend requests. Pruned on write.
_last_forgot_request_at: dict[str, datetime] = {}
_COOLDOWN_TRACKED_EMAILS_LIMIT = 1000


def generate_reset_token() -> tuple[str, str]:
    """Return a ``(raw_token, sha256_hex_digest)`` pair for one reset grant."""
    raw_token = secrets.token_urlsafe(RESET_TOKEN_BYTES)
    return raw_token, hash_reset_token(raw_token)


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def reset_link(raw_token: str) -> str:
    return f"{config.FRONTEND_ORIGIN.rstrip('/')}/reset-password?token={raw_token}"


def utcnow() -> datetime:
    """Naive-UTC clock, matching the codebase's DateTime convention."""
    return datetime.now()


def is_cooldown_active(email: str, now: datetime | None = None) -> bool:
    """Whether a forgot-password request for `email` must be suppressed."""
    now = now or utcnow()
    last = _last_forgot_request_at.get(email)
    if last is None:
        return False
    return (now - last).total_seconds() < RESEND_COOLDOWN_SECONDS


def record_forgot_request(email: str, now: datetime | None = None) -> None:
    now = now or utcnow()
    if len(_last_forgot_request_at) >= _COOLDOWN_TRACKED_EMAILS_LIMIT:
        oldest = sorted(_last_forgot_request_at.items(), key=lambda item: item[1])[
            : len(_last_forgot_request_at) // 2
        ]
        for key, _ in oldest:
            del _last_forgot_request_at[key]
    _last_forgot_request_at[email] = now


def clear_forgot_request_history() -> None:
    """Test hook: forget all resend-cooldown timestamps."""
    _last_forgot_request_at.clear()


def token_expiry(now: datetime | None = None) -> datetime:
    return (now or utcnow()) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)


def send_password_reset_email(to_email: str, link: str) -> bool:
    """Deliver the reset link. Returns False (never raises) when delivery
    is unconfigured or fails; the caller keeps the API response neutral."""
    if not config.SMTP_HOST:
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your Planora password"
    message["From"] = config.SMTP_FROM
    message["To"] = to_email
    message.set_content(
        "Hi there,\n\n"
        "Someone requested a password reset for your Planora account. "
        "If that was you, choose a new password here (this link expires "
        "in an hour and works only once):\n\n"
        f"{link}\n\n"
        "If you didn't ask for this, you can safely ignore this email — "
        "your password stays exactly as it is.\n\n"
        "— Planora"
    )
    try:
        if config.SMTP_USE_TLS:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
            try:
                server.starttls()
                if config.SMTP_USERNAME:
                    server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(message)
            finally:
                server.quit()
        else:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                if config.SMTP_USERNAME:
                    server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(message)
    except Exception:
        # Deliberately free of addresses, links, and tokens.
        logger.warning("Password reset email could not be delivered")
        return False
    return True
