from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.config import get_settings


@dataclass
class GenerationRequest:
    task_name: str
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1200
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    content: str
    provider: str
    model: str
    used_fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationErrorInfo:
    provider: str
    error_type: str
    message: str
    attempt: int
    retryable: bool
    status_code: Optional[int] = None

    def as_metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": self.provider,
            "error_type": self.error_type,
            "message": self.message,
            "attempt": self.attempt,
            "retryable": self.retryable,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        return payload


class ModelGateway:
    def __init__(self) -> None:
        settings = get_settings()
        self.default_model = settings.default_model
        self.openai_api_key = settings.openai_api_key
        self.anthropic_api_key = settings.anthropic_api_key
        self.request_timeout_seconds = settings.model_request_timeout_seconds
        self.max_retries = settings.model_max_retries

    def is_remote_available(self) -> bool:
        return bool(self.openai_api_key or self.anthropic_api_key)

    async def generate_text(
        self,
        request: GenerationRequest,
        *,
        fallback: Callable[[], str],
    ) -> GenerationResult:
        remote_error: Optional[GenerationErrorInfo] = None
        selected_provider = self._select_provider()
        if self.is_remote_available():
            remote_result, remote_error = await self._try_remote_generation(request)
            if remote_result is not None:
                return remote_result

        metadata = self._base_metadata(request)
        metadata.update(
            {
                "selected_provider": selected_provider,
                "request_timeout_seconds": self.request_timeout_seconds,
                "used_fallback": True,
            }
        )
        if remote_error is not None:
            metadata["remote_error"] = remote_error.as_metadata()
        elif not self.is_remote_available():
            metadata["remote_status"] = "skipped_no_provider"

        return GenerationResult(
            content=fallback(),
            provider="local-fallback",
            model="heuristic-v1",
            used_fallback=True,
            metadata=metadata,
        )

    async def _try_remote_generation(
        self,
        request: GenerationRequest,
    ) -> tuple[Optional[GenerationResult], Optional[GenerationErrorInfo]]:
        provider = self._select_provider()
        if provider is None:
            return None, None

        last_error: Optional[GenerationErrorInfo] = None
        for attempt in range(self.max_retries + 1):
            try:
                if provider == "anthropic":
                    result = await self._generate_with_anthropic(request)
                elif provider == "openai":
                    result = await self._generate_with_openai(request)
                else:
                    result = None
                if result is not None:
                    result.metadata = {
                        **self._base_metadata(request),
                        **result.metadata,
                        "attempt": attempt + 1,
                        "selected_provider": provider,
                        "request_timeout_seconds": self.request_timeout_seconds,
                        "used_fallback": False,
                    }
                    return result, None
            except Exception as exc:  # pragma: no cover - runtime integration path
                last_error = self._classify_remote_error(
                    provider=provider,
                    exc=exc,
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries and last_error.retryable:
                    await asyncio.sleep(min(1.5 * (attempt + 1), 5.0))
                    continue
                return None, last_error
        return None, None

    def _should_use_anthropic(self) -> bool:
        if not self.anthropic_api_key:
            return False
        return "claude" in self.default_model.lower()

    def _select_provider(self) -> Optional[str]:
        if self._should_use_anthropic():
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return None

    def _base_metadata(self, request: GenerationRequest) -> dict[str, Any]:
        return {
            "task_name": request.task_name,
            **request.metadata,
        }

    def _classify_remote_error(
        self,
        *,
        provider: str,
        exc: Exception,
        attempt: int,
    ) -> GenerationErrorInfo:
        status_code = getattr(exc, "status_code", None)
        message = str(exc).strip() or exc.__class__.__name__
        message_lower = message.lower()
        error_name = exc.__class__.__name__.lower()

        if isinstance(exc, asyncio.TimeoutError) or "timeout" in error_name:
            return GenerationErrorInfo(
                provider=provider,
                error_type="timeout",
                message=message,
                attempt=attempt,
                retryable=True,
                status_code=status_code,
            )

        if status_code in (401, 403) or any(
            token in error_name for token in ("authentication", "permission", "auth")
        ):
            return GenerationErrorInfo(
                provider=provider,
                error_type="auth",
                message=message,
                attempt=attempt,
                retryable=False,
                status_code=status_code,
            )

        if status_code == 429 or any(
            token in error_name for token in ("ratelimit", "rate_limit", "too_many_requests")
        ):
            return GenerationErrorInfo(
                provider=provider,
                error_type="rate_limit",
                message=message,
                attempt=attempt,
                retryable=True,
                status_code=status_code,
            )

        if any(
            marker in message_lower for marker in ("empty output_text", "empty content", "empty response")
        ):
            return GenerationErrorInfo(
                provider=provider,
                error_type="empty_response",
                message=message,
                attempt=attempt,
                retryable=False,
                status_code=status_code,
            )

        if (
            (status_code is not None and int(status_code) >= 500)
            or "temporarily unavailable" in message_lower
            or "service unavailable" in message_lower
            or any(
                token in error_name
                for token in (
                    "connection",
                    "overloaded",
                    "apierror",
                    "apiconnection",
                    "serviceunavailable",
                    "internalserver",
                )
            )
        ):
            return GenerationErrorInfo(
                provider=provider,
                error_type="provider_unavailable",
                message=message,
                attempt=attempt,
                retryable=True,
                status_code=status_code,
            )

        return GenerationErrorInfo(
            provider=provider,
            error_type="unknown",
            message=message,
            attempt=attempt,
            retryable=False,
            status_code=status_code,
        )

    async def _generate_with_openai(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.openai_api_key)
        response = await asyncio.wait_for(
            client.responses.create(
                model=self.default_model,
                instructions=request.system_prompt,
                input=request.prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_tokens,
            ),
            timeout=self.request_timeout_seconds,
        )
        content = getattr(response, "output_text", "") or ""
        if not content:
            raise RuntimeError("OpenAI returned empty output_text.")
        return GenerationResult(
            content=content,
            provider="openai",
            model=self.default_model,
            metadata={},
        )

    async def _generate_with_anthropic(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.anthropic_api_key)
        response = await asyncio.wait_for(
            client.messages.create(
                model=self.default_model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system_prompt or "",
                messages=[
                    {
                        "role": "user",
                        "content": request.prompt,
                    }
                ],
            ),
            timeout=self.request_timeout_seconds,
        )
        chunks: list[str] = []
        for item in response.content:
            text = getattr(item, "text", None)
            if text:
                chunks.append(text)
        content = "".join(chunks).strip()
        if not content:
            raise RuntimeError("Anthropic returned empty content.")
        return GenerationResult(
            content=content,
            provider="anthropic",
            model=self.default_model,
            metadata={},
        )


model_gateway = ModelGateway()
