from fastapi import APIRouter, Depends, Request, status
from datetime import datetime, timezone
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from api.deps.rate_limit import RateLimitDep
from core.errors import AppError
from core.rate_limit import RateLimiter
from core.security import (
    create_access_token,
    create_refresh_token_expiry,
    generate_refresh_token_raw,
    hash_refresh_token,
)
from db.session import transactional
from models.refresh_token import RefreshToken
from models.user import User
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserRead
from services.auth_service import authenticate_user, register_user


router = APIRouter()

_register_rate_limiter = RateLimiter(
    requests_per_minute=3,
    requests_per_hour=10,
    burst_size=3,
)


async def register_rate_limit(
    request: Request,
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"register:{client_ip}"
    allowed, info = await _register_rate_limiter.check_rate_limit(identifier)
    if not allowed:
        raise AppError(
            code="auth.register_rate_limited",
            message="Too many registration attempts. Please try again later.",
            status_code=429,
            metadata={"retry_after": info["retry_after"]},
        )


RegisterRateLimitDep = Depends(register_rate_limit)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    _rate_limit: None = RegisterRateLimitDep,
) -> TokenResponse:
    async with transactional(session):
        user = await register_user(session, payload)
        access_token = create_access_token(str(user.id))
        rt_raw = generate_refresh_token_raw()
        rt_hash = hash_refresh_token(rt_raw)
        rt_record = RefreshToken(
            token_hash=rt_hash,
            user_id=user.id,
            expires_at=create_refresh_token_expiry(),
        )
        session.add(rt_record)
        await session.flush()
        await session.refresh(rt_record)

    from core.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=rt_raw,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    async with transactional(session):
        user = await authenticate_user(session, payload)
        access_token = create_access_token(str(user.id))
        rt_raw = generate_refresh_token_raw()
        rt_hash = hash_refresh_token(rt_raw)
        rt_record = RefreshToken(
            token_hash=rt_hash,
            user_id=user.id,
            expires_at=create_refresh_token_expiry(),
        )
        session.add(rt_record)
        await session.flush()
        await session.refresh(rt_record)

    from core.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=rt_raw,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    from datetime import datetime, timezone

    from sqlalchemy import select

    async with transactional(session):
        rt_hash = hash_refresh_token(payload.refresh_token)
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == rt_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        rt_record = result.scalar_one_or_none()
        if not rt_record:
            raise AppError(
                code="auth.invalid_or_expired_refresh",
                message="Refresh token is invalid or has expired.",
                status_code=401,
            )

        access_token = create_access_token(str(rt_record.user_id))
        new_rt_raw = generate_refresh_token_raw()
        new_rt_hash = hash_refresh_token(new_rt_raw)
        rt_record.token_hash = new_rt_hash
        rt_record.expires_at = create_refresh_token_expiry()

    from core.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_rt_raw,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead(id=rt_record.user_id, email=(await session.get(User, rt_record.user_id)).email),
    )


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    from sqlalchemy import select, update

    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return {"message": "Logged out successfully"}

