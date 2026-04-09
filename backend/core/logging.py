import logging
import re
from typing import Any

from core.trace import get_trace_id

SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"password\s*[:=]\s*[^\s'\"]+", re.IGNORECASE), "password=***"),
    (re.compile(r"passwd\s*[:=]\s*[^\s'\"]+", re.IGNORECASE), "passwd=***"),
    (re.compile(r"pwd\s*[:=]\s*[^\s'\"]+", re.IGNORECASE), "pwd=***"),
    (re.compile(r"token\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "token=***"),
    (re.compile(r"access_token\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "access_token=***"),
    (re.compile(r"refresh_token\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "refresh_token=***"),
    (re.compile(r"api_key\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "api_key=***"),
    (re.compile(r"apikey\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "apikey=***"),
    (re.compile(r"secret\s*[:=]\s*[^\s'\"]{8,}", re.IGNORECASE), "secret=***"),
    (re.compile(r"authorization\s*[:=]\s*bearer\s+[^\s'\"]+", re.IGNORECASE), "authorization=bearer ***"),
]

SENSITIVE_KEYS: set[str] = {
    "password", "passwd", "pwd", "token", "access_token",
    "refresh_token", "api_key", "apikey", "secret", "authorization",
    "cookie", "session_id", "sessionid", "credit_card", "ssn",
}


def _redact_value(value: str) -> str:
    redacted = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _redict_dict(d: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    if depth > 5:
        return {"***": "[max depth exceeded]"}
    result: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(k, str) and any(sk in k.lower() for sk in SENSITIVE_KEYS):
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = _redict_dict(v, depth + 1)
        elif isinstance(v, str):
            result[k] = _redact_value(v)
        else:
            result[k] = v
    return result


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = get_trace_id()
        msg = super().format(record)
        return _redact_value(msg)


LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "[%(trace_id)s] [%(filename)s:%(lineno)d] %(message)s"
)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = RedactingFormatter(fmt=LOG_FORMAT)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level.upper())
    for name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    return logger


def sanitize_log_extra(extra: dict[str, Any]) -> dict[str, Any]:
    return _redict_dict(extra)
