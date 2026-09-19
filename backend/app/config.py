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
