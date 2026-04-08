from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
from core.errors import AppError


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def transactional(session: AsyncSession):
    try:
        yield session
        await session.commit()
    except AppError:
        await session.rollback()
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise AppError(
            code="db.transaction_failed",
            message=f"Database transaction failed: {exc}",
            status_code=500,
        ) from exc
    except Exception:
        await session.rollback()
        raise
