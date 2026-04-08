from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.config import get_settings
from core.errors import AppError


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire_at,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise AppError(
                code="auth.invalid_token_type",
                message="Expected access token.",
                status_code=401,
            )
        return payload
    except JWTError as exc:
        raise AppError(
            code="auth.invalid_token",
            message="Invalid or expired access token.",
            status_code=401,
        ) from exc


def generate_refresh_token_raw() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_refresh_token_value() -> str:
    raw = generate_refresh_token_raw()
    return hash_refresh_token(raw)


def create_refresh_token_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def decode_refresh_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise AppError(
                code="auth.invalid_token_type",
                message="Expected refresh token.",
                status_code=401,
            )
        return payload
    except JWTError as exc:
        raise AppError(
            code="auth.invalid_refresh_token",
            message="Invalid or expired refresh token.",
            status_code=401,
        ) from exc

