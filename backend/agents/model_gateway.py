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
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1200
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    content: str
    provider: str
    model: str
    cost: float = 0.0
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
        self.gateway_api_key = settings.model_gateway_api_key or settings.openai_api_key
        self.gateway_base_url = settings.model_gateway_base_url
        self.openai_api_key = settings.openai_api_key
        self.anthropic_api_key = settings.anthropic_api_key
        self.request_timeout_seconds = settings.model_request_timeout_seconds
        self.max_retries = settings.model_max_retries

    def is_remote_available(self) -> bool:
        return bool(self.gateway_api_key or self.openai_api_key or self.anthropic_api_key)

    async def generate_text(
        self,
        request: GenerationRequest,
        *,
        fallback: Callable[[], str],
    ) -> GenerationResult:
        from services.prompt_cache_service import prompt_cache_service

        cached = await prompt_cache_service.get(
            prefix=request.task_name,
            prompt=request.prompt,
            system_prompt=request.system_prompt,
        )
        if cached:
            return GenerationResult(
                content=cached,
                provider="cache-hit",
                model=self._resolve_model(request),
                cost=0.0,
                metadata={**self._base_metadata(request), "cache_hit": True},
            )

        remote_error: Optional[GenerationErrorInfo] = None
        remote_status: Optional[str] = None
        selected_provider = self._select_provider_compat(request)
        if self.is_remote_available():
            remote_result, remote_error = await self._try_remote_generation(request)
            if remote_result is not None:
                await prompt_cache_service.set(
                    prefix=request.task_name,
                    prompt=request.prompt,
                    system_prompt=request.system_prompt,
                    content=remote_result.content,
                )
                return remote_result
            if remote_error is not None:
                remote_status = "failed"
            else:
                remote_status = "skipped_no_provider"

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
        elif remote_status is not None:
            metadata["remote_status"] = remote_status
        elif not self.is_remote_available():
            metadata["remote_status"] = "skipped_no_provider"

        return GenerationResult(
            content=fallback(),
            provider="local-fallback",
            model="heuristic-v1",
            cost=0.0,
            used_fallback=True,
            metadata=metadata,
        )

    async def generate_text_async(
        self,
        request: GenerationRequest,
        *,
        fallback: Callable[[], str],
    ) -> GenerationResult:
        return await self.generate_text(request, fallback=fallback)

    def generate_text_sync(
        self,
        request: GenerationRequest,
        *,
        fallback: Callable[[], str],
    ) -> GenerationResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return asyncio.run(self.generate_text(request, fallback=fallback))

        import concurrent.futures

        def _run_in_worker() -> GenerationResult:
            try:
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(
                        self.generate_text(request, fallback=fallback)
                    )
                finally:
                    new_loop.close()
            except Exception as exc:
                from core.logging import get_logger
                logger = get_logger(__name__)
                logger.warning(
                    "model_gateway_sync_generation_failed",
                    extra={"error": str(exc), "task_name": request.task_name},
                )
                return GenerationResult(
                    content=fallback(),
                    provider="fallback",
                    model=request.model,
                    usage=None,
                    cached=False,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_worker)
            from core.config import get_settings
            return future.result(timeout=get_settings().model_gateway_sync_timeout_seconds)

    FALLBACK_CHAIN: dict[str, list[str]] = {
        "claude-sonnet-4": ["claude-haiku-3", "gpt-4o"],
        "claude-haiku-3": ["deepseek-v3", "gpt-4o-mini"],
        "deepseek-v3": ["gpt-4o-mini"],
        "gpt-4o": ["gpt-4o-mini"],
        "gpt-4o-mini": [],
        "claude-opus-3": ["claude-sonnet-4", "gpt-4o"],
        "claude-sonnet-3-5": ["claude-sonnet-4", "gpt-4o"],
    }

    async def _try_remote_generation(
        self,
        request: GenerationRequest,
    ) -> tuple[Optional[GenerationResult], Optional[GenerationErrorInfo]]:
        provider = self._select_provider_compat(request)
        if provider is None:
            return None, None

        last_error: Optional[GenerationErrorInfo] = None
        for attempt in range(self.max_retries + 1):
            try:
                if provider == "anthropic":
                    result = await self._generate_with_anthropic(request)
                elif provider == "openai-compatible":
                    result = await self._generate_with_openai_compatible(request)
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
            except (
                ConnectionError,
                TimeoutError,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                last_error = self._classify_remote_error(
                    provider=provider,
                    exc=exc,
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries and last_error.retryable:
                    await asyncio.sleep(min(1.5 * (attempt + 1), 5.0))
                    continue

        fallback_models = self.FALLBACK_CHAIN.get(request.model or self.default_model, [])
        for fallback_model in fallback_models:
            try:
                fallback_request = GenerationRequest(
                    task_name=request.task_name,
                    prompt=request.prompt,
                    system_prompt=request.system_prompt,
                    model=fallback_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    metadata={**request.metadata, "original_model": request.model},
                )
                result = await self._generate_with_openai_compatible(fallback_request)
                if result is not None:
                    result.metadata = {
                        **self._base_metadata(request),
                        **result.metadata,
                        "attempt": 1,
                        "selected_provider": provider,
                        "used_fallback": True,
                        "fallback_from": request.model,
                        "fallback_to": fallback_model,
                    }
                    return result, None
            except (ConnectionError, TimeoutError, OSError, asyncio.TimeoutError):
                continue

        return None, last_error

    def _should_use_anthropic(self) -> bool:
        if not self.anthropic_api_key:
            return False
        return "claude" in self.default_model.lower()

    def _select_provider(self, request: Optional[GenerationRequest] = None) -> Optional[str]:
        requested_model = self._resolve_model(request).lower()
        if self.gateway_api_key or self.openai_api_key:
            return "openai-compatible"
        if "claude" in requested_model and self.anthropic_api_key:
            return "anthropic"
        if self.anthropic_api_key:
            return "anthropic"
        return None

    def _base_metadata(self, request: GenerationRequest) -> dict[str, Any]:
        return {
            "task_name": request.task_name,
            "requested_model": self._resolve_model(request),
            **request.metadata,
        }

    def _resolve_model(self, request: Optional[GenerationRequest]) -> str:
        if request is None:
            return self.default_model
        return request.model or self.default_model

    def _route_to_tier(self, request: GenerationRequest) -> str:
        task_name = request.task_name.lower()
        if request.system_prompt and len(request.system_prompt) > 3000:
            return "t2"
        if any(kw in task_name for kw in ["outline", "structure", "plan"]):
            return "t1"
        if any(kw in task_name for kw in ["revision", "edit", "rewrite", "debate"]):
            return "t2"
        if any(kw in task_name for kw in ["linguistic", "canon", "consistency"]):
            return "t2"
        if any(kw in task_name for kw in ["librarian", "architect", "approver"]):
            return "t1"
        if any(kw in task_name for kw in ["chaos_analysis", "beta_reader", "writer.draft"]):
            return "t2"
        if any(kw in task_name for kw in ["tension", "social", "character_arc"]):
            return "t2"
        if request.max_tokens and request.max_tokens < 300:
            return "t1"
        if request.temperature and request.temperature > 0.7:
            return "t3"
        return "t2"

    def _calculate_cost(
        self,
        usage: Any,
        model: str,
    ) -> float:
        if usage is None:
            return 0.0
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        model_lower = model.lower()

        if "claude" in model_lower:
            input_rate = 3.0 / 1_000_000
            output_rate = 15.0 / 1_000_000
        elif "gpt-4o" in model_lower:
            input_rate = 2.5 / 1_000_000
            output_rate = 10.0 / 1_000_000
        elif "gpt-4o-mini" in model_lower:
            input_rate = 0.15 / 1_000_000
            output_rate = 0.6 / 1_000_000
        elif "gpt-4-turbo" in model_lower:
            input_rate = 10.0 / 1_000_000
            output_rate = 30.0 / 1_000_000
        elif "gpt-4" in model_lower:
            input_rate = 30.0 / 1_000_000
            output_rate = 60.0 / 1_000_000
        elif "deepseek" in model_lower:
            input_rate = 0.27 / 1_000_000
            output_rate = 1.1 / 1_000_000
        elif "text-embedding" in model_lower:
            return input_tokens * 0.13 / 1_000_000
        else:
            input_rate = 1.0 / 1_000_000
            output_rate = 2.0 / 1_000_000

        return round(input_tokens * input_rate + output_tokens * output_rate, 6)

    def _select_provider_compat(
        self,
        request: Optional[GenerationRequest] = None,
    ) -> Optional[str]:
        try:
            return self._select_provider(request)
        except TypeError:
            # 兼容旧测试中把 _select_provider monkeypatch 成无参 lambda 的写法。
            return self._select_provider()  # type: ignore[misc]

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

    async def _generate_with_openai_compatible(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        from openai import AsyncOpenAI

        client_kwargs: dict[str, Any] = {
            "api_key": self.gateway_api_key or self.openai_api_key,
            "max_retries": 0,
            "timeout": self.request_timeout_seconds,
        }
        if self.gateway_base_url:
            client_kwargs["base_url"] = self.gateway_base_url
        client = AsyncOpenAI(**client_kwargs)
        api_mode = self._resolve_openai_compatible_api_mode(request)

        if api_mode == "chat_completions":
            request_kwargs: dict[str, Any] = {
                "model": self._resolve_model(request),
                "messages": self._build_chat_messages(request),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            if request.reasoning_effort and self._supports_chat_reasoning_effort(request):
                # 云雾的 chat 兼容格式支持直接携带 reasoning_effort。
                request_kwargs["reasoning_effort"] = request.reasoning_effort
            response = await asyncio.wait_for(
                client.chat.completions.create(**request_kwargs),
                timeout=self.request_timeout_seconds,
            )
            content = self._extract_chat_completion_text(response)
            if not content:
                raise RuntimeError("OpenAI-compatible chat provider returned empty content.")
            usage = getattr(response, "usage", None)
            cost = self._calculate_cost(usage, self._resolve_model(request))
        else:
            request_kwargs = {
                "model": self._resolve_model(request),
                "instructions": request.system_prompt,
                "input": request.prompt,
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
            }
            if request.reasoning_effort:
                request_kwargs["reasoning"] = {"effort": request.reasoning_effort}
            response = await asyncio.wait_for(
                client.responses.create(**request_kwargs),
                timeout=self.request_timeout_seconds,
            )
            content = getattr(response, "output_text", "") or ""
            if not content:
                raise RuntimeError("OpenAI-compatible provider returned empty output_text.")
            usage = getattr(response, "usage", None)
            cost = self._calculate_cost(usage, self._resolve_model(request))
        return GenerationResult(
            content=content,
            provider="openai-compatible",
            model=self._resolve_model(request),
            cost=cost,
            metadata={
                "base_url": self.gateway_base_url,
                "api_mode": api_mode,
            },
        )

    def _resolve_openai_compatible_api_mode(
        self,
        request: Optional[GenerationRequest] = None,
    ) -> str:
        model_name = self._resolve_model(request).lower()
        if any(token in model_name for token in ("gemini", "claude", "deepseek")):
            return "chat_completions"
        return "responses"

    def _build_chat_messages(
        self,
        request: GenerationRequest,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": request.system_prompt,
                }
            )
        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )
        return messages

    def _supports_chat_reasoning_effort(
        self,
        request: Optional[GenerationRequest] = None,
    ) -> bool:
        model_name = self._resolve_model(request).lower()
        if "claude" in model_name:
            return False
        return True

    def _extract_chat_completion_text(self, response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                    else:
                        text = getattr(item, "text", None)
                    if text:
                        parts.append(str(text))
                if parts:
                    return "".join(parts).strip()
        return ""

    async def _generate_with_anthropic(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.anthropic_api_key)
        response = await asyncio.wait_for(
            client.messages.create(
                model=self._resolve_model(request),
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
            model=self._resolve_model(request),
            cost=0.0,
            metadata={},
        )


model_gateway = ModelGateway()
