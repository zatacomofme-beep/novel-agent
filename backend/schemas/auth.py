from uuid import UUID

from pydantic import EmailStr, Field

from schemas.base import ORMModel


class RegisterRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(ORMModel):
    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")


class UserRead(ORMModel):
    id: UUID
    email: EmailStr


class TokenResponse(ORMModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user: UserRead
