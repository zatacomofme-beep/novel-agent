from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock

from agents.model_gateway import GenerationErrorInfo, GenerationRequest, ModelGateway


class AuthenticationError(Exception):
    def __init__(self, message: str = "invalid key") -> None:
        super().__init__(message)
        self.status_code = 401


class RateLimitError(Exception):
    def __init__(self, message: str = "rate limited") -> None:
        super().__init__(message)
        self.status_code = 429


class InternalServerError(Exception):
    def __init__(self, message: str = "service unavailable") -> None:
        super().__init__(message)
        self.status_code = 503


class ModelGatewayTests(unittest.IsolatedAsyncioTestCase):
    def test_openai_compatible_api_mode_routing(self) -> None:
        gateway = ModelGateway()

        self.assertEqual(
            gateway._resolve_openai_compatible_api_mode(
                GenerationRequest(task_name="x", prompt="hi", model="gpt-5.4")
            ),
            "responses",
        )
        self.assertEqual(
            gateway._resolve_openai_compatible_api_mode(
                GenerationRequest(task_name="x", prompt="hi", model="gemini-3.1-pro-preview")
            ),
            "chat_completions",
        )
        self.assertEqual(
            gateway._resolve_openai_compatible_api_mode(
                GenerationRequest(task_name="x", prompt="hi", model="claude-opus-4-6")
            ),
            "chat_completions",
        )
        self.assertEqual(
            gateway._resolve_openai_compatible_api_mode(
                GenerationRequest(task_name="x", prompt="hi", model="deepseek-v3.2")
            ),
            "chat_completions",
        )

    def test_extract_chat_completion_text_supports_string_and_part_list(self) -> None:
        gateway = ModelGateway()

        class _Message:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Message(content)

        class _Response:
            def __init__(self, choices):
                self.choices = choices

        string_response = _Response([_Choice("直接字符串内容")])
        list_response = _Response([_Choice([{"text": "分片"}, {"text": "拼接"}])])

        self.assertEqual(gateway._extract_chat_completion_text(string_response), "直接字符串内容")
        self.assertEqual(gateway._extract_chat_completion_text(list_response), "分片拼接")

    def test_supports_chat_reasoning_effort_is_disabled_for_claude(self) -> None:
        gateway = ModelGateway()

        self.assertTrue(
            gateway._supports_chat_reasoning_effort(
                GenerationRequest(task_name="x", prompt="hi", model="gemini-3.1-pro-preview")
            )
        )
        self.assertTrue(
            gateway._supports_chat_reasoning_effort(
                GenerationRequest(task_name="x", prompt="hi", model="deepseek-v3.2")
            )
        )
        self.assertFalse(
            gateway._supports_chat_reasoning_effort(
                GenerationRequest(task_name="x", prompt="hi", model="claude-opus-4-6")
            )
        )

    async def test_generate_text_marks_skipped_remote_when_no_provider(self) -> None:
        gateway = ModelGateway()
        gateway.openai_api_key = None
        gateway.anthropic_api_key = None
        gateway.gateway_api_key = None

        result = await gateway.generate_text(
            GenerationRequest(task_name="writer.draft", prompt="hello"),
            fallback=lambda: "fallback content",
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.provider, "local-fallback")
        self.assertEqual(result.content, "fallback content")
        self.assertEqual(result.metadata["remote_status"], "skipped_no_provider")

    async def test_generate_text_surfaces_structured_remote_error(self) -> None:
        gateway = ModelGateway()
        gateway.openai_api_key = "test-key"
        gateway.anthropic_api_key = None
        gateway._select_provider = lambda: "openai"  # type: ignore[method-assign]
        gateway._try_remote_generation = AsyncMock(  # type: ignore[method-assign]
            return_value=(
                None,
                GenerationErrorInfo(
                    provider="openai",
                    error_type="rate_limit",
                    message="too many requests",
                    attempt=2,
                    retryable=True,
                    status_code=429,
                ),
            )
        )

        result = await gateway.generate_text(
            GenerationRequest(task_name="writer.draft", prompt="hello"),
            fallback=lambda: "fallback content",
        )

        self.assertTrue(result.used_fallback)
        self.assertEqual(result.metadata["remote_error"]["error_type"], "rate_limit")
        self.assertEqual(result.metadata["remote_error"]["status_code"], 429)

    async def test_generate_text_sync_returns_result_inside_running_loop(self) -> None:
        gateway = ModelGateway()
        gateway.openai_api_key = None
        gateway.anthropic_api_key = None

        result = gateway.generate_text_sync(
            GenerationRequest(task_name="writer.draft", prompt="hello"),
            fallback=lambda: "fallback content",
        )

        self.assertEqual(result.content, "fallback content")
        self.assertTrue(result.used_fallback)

    def test_classify_remote_errors(self) -> None:
        gateway = ModelGateway()

        timeout = gateway._classify_remote_error(
            provider="openai",
            exc=asyncio.TimeoutError(),
            attempt=1,
        )
        auth = gateway._classify_remote_error(
            provider="openai",
            exc=AuthenticationError(),
            attempt=1,
        )
        rate_limit = gateway._classify_remote_error(
            provider="openai",
            exc=RateLimitError(),
            attempt=1,
        )
        empty_response = gateway._classify_remote_error(
            provider="openai",
            exc=RuntimeError("OpenAI returned empty output_text."),
            attempt=1,
        )
        provider_unavailable = gateway._classify_remote_error(
            provider="openai",
            exc=InternalServerError(),
            attempt=1,
        )
        unknown = gateway._classify_remote_error(
            provider="openai",
            exc=ValueError("weird"),
            attempt=1,
        )

        self.assertEqual(timeout.error_type, "timeout")
        self.assertTrue(timeout.retryable)
        self.assertEqual(auth.error_type, "auth")
        self.assertFalse(auth.retryable)
        self.assertEqual(rate_limit.error_type, "rate_limit")
        self.assertTrue(rate_limit.retryable)
        self.assertEqual(empty_response.error_type, "empty_response")
        self.assertEqual(provider_unavailable.error_type, "provider_unavailable")
        self.assertEqual(unknown.error_type, "unknown")
