from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BusEvent:
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=utcnow)
