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
    async def test_generate_text_marks_skipped_remote_when_no_provider(self) -> None:
        gateway = ModelGateway()
        gateway.openai_api_key = None
        gateway.anthropic_api_key = None

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
