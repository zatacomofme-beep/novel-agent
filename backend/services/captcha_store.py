from __future__ import annotations

import uuid
from typing import Final

import redis

from core.config import get_settings
from services.captcha_service import generate_captcha

CAPTCHA_EXPIRE_SECONDS: Final = 300


def _get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def generate_and_store_captcha() -> tuple[str, str]:
    captcha = generate_captcha()
    session_id = str(uuid.uuid4())
    client = _get_redis_client()
    client.setex(f"captcha:{session_id}", CAPTCHA_EXPIRE_SECONDS, captcha.answer)
    return session_id, captcha.image_base64


def verify_captcha(session_id: str, answer: str) -> bool:
    client = _get_redis_client()
    stored = client.get(f"captcha:{session_id}")
    if stored and stored.lower() == answer.lower():
        client.delete(f"captcha:{session_id}")
        return True
    return False
