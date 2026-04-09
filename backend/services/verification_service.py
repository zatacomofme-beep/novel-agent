from __future__ import annotations

import logging
import random
import string
from typing import Final

import redis

from core.config import get_settings

CAPTCHA_CODE_LENGTH: Final = 6
CAPTCHA_CODE_EXPIRE_SECONDS: Final = 300

logger = logging.getLogger(__name__)


def _get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def send_verification_code(email: str) -> bool:
    code = "".join(random.choices(string.digits, k=CAPTCHA_CODE_LENGTH))
    client = _get_redis_client()
    key = f"email_verification:{email}"
    client.setex(key, CAPTCHA_CODE_EXPIRE_SECONDS, code)
    settings = get_settings()
    if settings.email_enabled:
        _send_email(email, code)
        return True
    return False


def _send_email(email: str, code: str) -> None:
    settings = get_settings()
    if not settings.email_smtp_host:
        return
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(f"您的验证码是：{code}，5 分钟内有效。")
    msg["Subject"] = "验证码"
    msg["From"] = settings.email_from_address
    msg["To"] = email
    try:
        with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
            if settings.email_smtp_tls:
                server.starttls()
            if settings.email_username and settings.email_password:
                server.login(settings.email_username, settings.email_password)
            server.send_message(msg)
    except Exception as e:
        logger.warning("Email sending failed: %s", e)


def verify_code(email: str, code: str) -> bool:
    client = _get_redis_client()
    key = f"email_verification:{email}"
    stored_code = client.get(key)
    if stored_code and stored_code == code:
        client.delete(key)
        return True
    return False
