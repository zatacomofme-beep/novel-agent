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
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BASE_DELAY = 1.0

    def __init__(
        self,
        name: str,
        role: str,
        *,
        bus: Optional[InMemoryMessageBus] = None,
        max_retries: int | None = None,
        output_schema: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.role = role
        self.bus = bus or message_bus
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.output_schema = output_schema

    async def run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._run_with_tracing(context, payload)
                if response.success and self.output_schema is not None and response.data is not None:
                    from agents.output_validator import safe_validate_agent_output
                    validated, validation_err = safe_validate_agent_output(
                        response.data,
                        self.output_schema,
                        agent_name=self.name,
                    )
                    if validation_err:
                        last_error = str(validation_err)
                        if attempt < self.max_retries:
                            import asyncio
                            delay = self.DEFAULT_BASE_DELAY * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue
                        return AgentResponse(
                            success=False,
                            data=None,
                            error=last_error,
                            confidence=0.0,
                            reasoning=f"{self.name} output schema validation failed after {self.max_retries + 1} attempts",
                        )
                    if validated is not None:
                        response.data = validated.model_dump(mode="json")
                return response
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    import asyncio
                    delay = self.DEFAULT_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        fallback_response = await self._fallback(context, payload, last_error)
        if fallback_response is not None:
            return fallback_response
        return AgentResponse(
            success=False,
            data=None,
            error=last_error or "unknown",
            confidence=0.0,
            reasoning=f"{self.name} failed after {self.max_retries + 1} attempts",
        )

    async def _run_with_tracing(
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

    async def _fallback(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
        error: str | None,
    ) -> AgentResponse | None:
        return None

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
