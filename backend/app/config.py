import os

from dotenv import load_dotenv

# Load backend/.env for local development. Production platforms provide
# real environment variables, which always take precedence.
load_dotenv()


# JWT_SECRET_KEY must be provided via the environment (backend/.env for
# local development, hosting platform variables in production). There is
# intentionally no default: starting without a secret must fail loudly.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not set. Set it to a long random secret, e.g. "
        "JWT_SECRET_KEY=replace-with-a-long-random-secret "
        "(see backend/.env.example)."
    )
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Frontend origin for CORS. Defaults to the local Vite dev server, preserving
# existing behavior; production supplies the deployed frontend URL.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


def _parse_origin_list(raw: str | None) -> list[str]:
    return [
        value.strip().rstrip("/")
        for value in (raw or "").split(",")
        if value.strip()
    ]


def _unique_origins(*groups: list[str]) -> list[str]:
    seen: list[str] = []
    for group in groups:
        for origin in group:
            if origin and origin not in seen:
                seen.append(origin)
    return seen


# Local development origins. Browsers running the Vite dev server need these
# even when the API itself is hosted remotely (e.g. local frontend talking
# to the Railway backend). Localhost-only entries cannot be abused by a
# remote attacker, so they are safe defaults in every environment.
LOCAL_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Full CORS allow-list: the production frontend plus local dev servers plus
# any extra operator-supplied origins (CORS_EXTRA_ORIGINS, comma-separated).
CORS_ALLOWED_ORIGINS = _unique_origins(
    [FRONTEND_ORIGIN],
    LOCAL_DEV_ORIGINS,
    _parse_origin_list(os.getenv("CORS_EXTRA_ORIGINS")),
)

# Frontend origins an OAuth flow may return to after authentication. The
# browser supplies its own origin via the signed `next` parameter; anything
# outside this list falls back to FRONTEND_ORIGIN (never an open redirect).
OAUTH_ALLOWED_RETURN_ORIGINS = _unique_origins(
    [FRONTEND_ORIGIN],
    LOCAL_DEV_ORIGINS,
    _parse_origin_list(os.getenv("OAUTH_ALLOWED_RETURN_ORIGINS")),
)

# Backend origin used to construct OAuth provider redirect URIs. The provider
# (Google, GitHub) must redirect the browser back to this origin's callback
# endpoint, which runs on the backend, not the frontend. Defaults to the local
# uvicorn dev server.
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")

# Web Push (VAPID) keys for browser notifications. The public key is exposed
# to authenticated frontends so they can subscribe via pushManager; the
# private key never leaves the server and is used when sending pushes.
# Empty until the operator generates a pair (see .env.example). Push
# subscription storage works without keys; actual delivery is enabled once
# keys are configured.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@planora.local")

# OAuth 2.0 credentials. Set these in backend/.env for local development or
# in the hosting platform's environment variables for production.
# Leave unset to disable the corresponding OAuth provider at runtime.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

# Secret used to sign CSRF state tokens for OAuth flows. Falls back to the
# JWT secret so existing single-secret deployments work without change, but
# a dedicated value is strongly recommended in production.
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", JWT_SECRET_KEY)
