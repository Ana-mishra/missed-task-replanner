from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must be a valid email address")
        return normalized


class RegisterRequest(Credentials):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class LoginRequest(Credentials):
    pass


class UserResponse(BaseModel):
    id: int
    name: str
    name_confirmed: bool
    email: str

    model_config = ConfigDict(from_attributes=True)

class UpdateNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must be a valid email address")
        return normalized


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match.")
        return self


class MessageResponse(BaseModel):
    message: str
    # Forgot-password only: the linked OAuth provider ("google"/"github")
    # when the account authenticates solely through it and therefore has no
    # local password to reset. Always None for password accounts, unknown
    # emails, and the reset-password endpoint.
    provider: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
