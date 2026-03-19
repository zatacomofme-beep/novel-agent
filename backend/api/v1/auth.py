from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from core.security import create_access_token
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from services.auth_service import authenticate_user, register_user


router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = await register_user(session, payload)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    user = await authenticate_user(session, payload)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
