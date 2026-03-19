from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from core.config import Settings, get_settings
from core.errors import AppError
from core.security import decode_access_token
from db.session import AsyncSessionLocal
from models.user import User
from services.auth_service import get_user_by_id


@lru_cache(maxsize=1)
def settings() -> Settings:
    return get_settings()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db_session() -> AsyncIterator:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session=Depends(get_db_session),
) -> User:
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if not subject:
        raise AppError(
            code="auth.invalid_token",
            message="Token payload is missing subject.",
            status_code=401,
        )

    user = await get_user_by_id(session, subject)
    if user is None:
        raise AppError(
            code="auth.user_not_found",
            message="Authenticated user does not exist.",
            status_code=401,
        )
    return user
