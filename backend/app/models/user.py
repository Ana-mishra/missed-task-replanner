from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.task import Task
from app.models.user_settings import UserSettings


class User(Base):
    """A local account used by the authentication foundation."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    tasks: Mapped[list["Task"]] = relationship(back_populates="owner")
    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
