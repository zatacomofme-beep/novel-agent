from uuid import UUID

from pydantic import EmailStr, Field

from schemas.base import ORMModel


class RegisterRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(ORMModel):
    id: UUID
    email: EmailStr


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
