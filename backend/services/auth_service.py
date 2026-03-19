from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from core.security import get_password_hash, verify_password
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    return await session.get(User, user_id)


async def register_user(session: AsyncSession, payload: RegisterRequest) -> User:
    existing = await get_user_by_email(session, payload.email)
    if existing is not None:
        raise AppError(
            code="auth.email_in_use",
            message="Email is already registered.",
            status_code=409,
        )

    user = User(
        email=payload.email.lower(),
        password_hash=get_password_hash(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, payload: LoginRequest) -> User:
    user = await get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(
            code="auth.invalid_credentials",
            message="Invalid email or password.",
            status_code=401,
        )
    return user
