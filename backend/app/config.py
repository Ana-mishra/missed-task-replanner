import os


# Deployments should set JWT_SECRET_KEY. The fallback keeps local development
# and tests usable without placing a secret in API route code.
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "development-only-change-me-before-production-2026"
)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
