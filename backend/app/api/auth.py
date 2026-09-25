import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.oauth_account import OAuthAccount
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateNameRequest,
    UserResponse,
)
from app.services import password_reset
from app.services.security import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from a valid Bearer access token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid_credentials
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise invalid_credentials

    user = db.get(User, user_id)
    if user is None:
        raise invalid_credentials
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == request.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
    name=request.name,
    name_confirmed=True,
    email=request.email,
    password_hash=hash_password(request.password),
)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if user is None or user.password_hash is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))
FORGOT_PASSWORD_RESPONSE = (
    "If an account exists for that email, we've sent you a password reset link."
)


OAUTH_SIGNIN_PROVIDERS = ("google", "github")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Start a password reset. Password accounts (with or without linked
    OAuth identities) follow the normal token flow and always receive the
    same neutral response. Accounts whose only credential is a linked
    OAuth identity get no token or email — instead the response names
    that provider so the client can point at the right sign-in button.
    Unknown emails stay fully neutral."""
    email = request.email
    user = db.query(User).filter(User.email == email).first()

    if user is not None and user.password_hash is None:
        linked = (
            db.query(OAuthAccount)
            .filter(OAuthAccount.user_id == user.id)
            .order_by(OAuthAccount.id)
            .all()
        )
        for account in linked:
            if account.provider in OAUTH_SIGNIN_PROVIDERS:
                return MessageResponse(
                    message=FORGOT_PASSWORD_RESPONSE, provider=account.provider
                )
        return MessageResponse(message=FORGOT_PASSWORD_RESPONSE)

    if user is not None and user.password_hash is not None:
        now = password_reset.utcnow()
        if not password_reset.is_cooldown_active(email, now):
            # Rotate: at most one usable token per user at any moment.
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            ).delete(synchronize_session=False)
            raw_token, token_hash = password_reset.generate_reset_token()
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=password_reset.token_expiry(now),
                )
            )
            db.commit()
            password_reset.record_forgot_request(email, now)
            password_reset.send_password_reset_email(email, password_reset.reset_link(raw_token))

    return MessageResponse(message=FORGOT_PASSWORD_RESPONSE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume a reset token and set a new password. The token lookup uses
    only its hash; success marks it used in the same commit as the update."""
    now = password_reset.utcnow()
    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == password_reset.hash_reset_token(request.token))
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid.",
        )
    if record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has already been used.",
        )
    if record.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired.",
        )

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid.",
        )

    user.password_hash = hash_password(request.password)
    record.used_at = now
    db.commit()
    return MessageResponse(message="Your password has been changed successfully.")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_me(
    request: UpdateNameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.name = request.name.strip()
    current_user.name_confirmed = True

    db.commit()
    db.refresh(current_user)

    return current_user