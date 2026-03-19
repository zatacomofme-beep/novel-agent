from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from typing import Optional

from bus.message_bus import InMemoryMessageBus, message_bus
from bus.protocol import AgentMessage, AgentResponse, MessageType, Priority


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AgentRunContext:
    chapter_id: str
    project_id: str
    task_id: str
    payload: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=utcnow)

    def add_trace(self, agent: str, data: dict[str, Any], reasoning: str) -> None:
        self.trace.append(
            {
                "agent": agent,
                "data": data,
                "reasoning": reasoning,
                "timestamp": utcnow().isoformat(),
            }
        )


class BaseAgent:
    def __init__(
        self,
        name: str,
        role: str,
        *,
        bus: Optional[InMemoryMessageBus] = None,
    ) -> None:
        self.name = name
        self.role = role
        self.bus = bus or message_bus

    async def run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        self._publish(
            recipients=["coordinator"],
            message_type=MessageType.STATE_UPDATE,
            subject=f"{self.name}.start",
            content={"payload_keys": sorted(payload.keys())},
        )
        response = await self._run(context, payload)
        if response.success:
            context.add_trace(
                self.name,
                response.data or {},
                response.reasoning,
            )
            self._publish(
                recipients=["coordinator"],
                message_type=MessageType.TASK_RESULT,
                subject=f"{self.name}.success",
                content={"confidence": response.confidence},
            )
        else:
            self._publish(
                recipients=["coordinator"],
                message_type=MessageType.ERROR,
                subject=f"{self.name}.error",
                content={"error": response.error or "unknown"},
                priority=Priority.HIGH,
            )
        return response

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        raise NotImplementedError

    def _publish(
        self,
        *,
        recipients: list[str],
        message_type: MessageType,
        subject: str,
        content: dict[str, Any],
        priority: Priority = Priority.NORMAL,
    ) -> None:
        self.bus.publish(
            AgentMessage(
                sender=self.name,
                recipients=recipients,
                message_type=message_type,
                priority=priority,
                subject=subject,
                content=content,
            )
        )
