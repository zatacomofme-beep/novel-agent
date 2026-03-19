from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageType(str, Enum):
    STATE_UPDATE = "STATE_UPDATE"
    INFO_REQUEST = "INFO_REQUEST"
    INFO_RESPONSE = "INFO_RESPONSE"
    TASK_ASSIGNMENT = "TASK_ASSIGNMENT"
    TASK_RESULT = "TASK_RESULT"
    ERROR = "ERROR"


class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


@dataclass
class AgentMessage:
    sender: str
    recipients: list[str]
    message_type: MessageType
    subject: str
    content: dict[str, Any]
    priority: Priority = Priority.NORMAL
    requires_response: bool = False
    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=utcnow)


@dataclass
class AgentResponse:
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 1.0
    reasoning: str = ""
