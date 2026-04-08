from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app


class AuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.v1.auth.register_user", new_callable=AsyncMock)
    def test_register_returns_201_with_tokens(self, mock_register: AsyncMock) -> None:
        mock_user = MagicMock()
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.email = "test@example.com"
        mock_register.return_value = mock_user

        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "strongpassword123"},
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertIn("expires_in", data)
        self.assertEqual(data["user"]["email"], "test@example.com")

    @patch("api.v1.auth.register_user", new_callable=AsyncMock)
    def test_register_rejects_short_password(self, _mock: AsyncMock) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        self.assertEqual(response.status_code, 422)

    @patch("api.v1.auth.authenticate_user", new_callable=AsyncMock)
    def test_login_returns_200_with_tokens(self, mock_auth: AsyncMock) -> None:
        mock_user = MagicMock()
        mock_user.id = "550e8400-e29b-41d4-a716-446655440001"
        mock_user.email = "user@example.com"
        mock_auth.return_value = mock_user

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")

    @patch("api.v1.auth.authenticate_user", new_callable=AsyncMock)
    def test_login_invalid_credentials_returns_error(self, mock_auth: AsyncMock) -> None:
        from core.errors import AppError
        mock_auth.side_effect = AppError(
            code="auth.invalid_credentials",
            message="Invalid email or password.",
            status_code=401,
        )

        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpass"},
        )

        self.assertEqual(response.status_code, 401)

    def test_me_without_auth_returns_401(self) -> None:
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 403)

    @patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock)
    def test_refresh_valid_token_rotates(self, mock_execute: AsyncMock) -> None:
        from datetime import datetime, timezone, timedelta
        from models.refresh_token import RefreshToken

        mock_rt = MagicMock(spec=RefreshToken)
        mock_rt.user_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_rt.token_hash = "valid_hash"
        mock_rt.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rt
        mock_execute.return_value = mock_result

        with patch("api.v1.auth.session.get") as mock_get:
            mock_user = MagicMock()
            mock_user.email = "user@example.com"
            mock_get.return_value = mock_user

            response = self.client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid_hash"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

    @patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock)
    def test_refresh_invalid_token_returns_401(self, mock_execute: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_execute.return_value = mock_result

        response = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_or_expired"},
        )

        self.assertEqual(response.status_code, 401)


class HealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_root_returns_status(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_ready_returns_api_prefix(self) -> None:
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertIn("api_prefix", response.json())


class CircuitBreakerTests(unittest.TestCase):
    from core.circuit_breaker import TokenCircuitBreaker

    def test_circuit_opens_on_budget_exceeded(self) -> None:
        cb = TokenCircuitBreaker(chapter_budget=0.01)
        result = cb.check_and_record(chapter_id="ch1", tokens_used=100, cost=0.02)
        self.assertTrue(result.should_break)
        self.assertEqual(result.reason, "exceeded_budget")

    def test_circuit_stays_closed_under_budget(self) -> None:
        cb = TokenCircuitBreaker(chapter_budget=10.0)
        result = cb.check_and_record(chapter_id="ch1", tokens_used=100, cost=0.5)
        self.assertFalse(result.should_break)
        self.assertIsNone(result.reason)

    def test_loop_detection_triggers_circuit_open(self) -> None:
        cb = TokenCircuitBreaker(
            loop_threshold_tokens=100,
            loop_count_trigger=2,
        )
        r1 = cb.check_and_record(chapter_id="ch1", tokens_used=200, cost=0.01)
        self.assertFalse(r1.should_break)
        r2 = cb.check_and_record(chapter_id="ch1", tokens_used=200, cost=0.01)
        self.assertFalse(r2.should_break)
        r3 = cb.check_and_record(chapter_id="ch1", tokens_used=200, cost=0.01)
        self.assertTrue(r3.should_break)
        self.assertEqual(r3.reason, "loop_detected")

    def test_records_capped_per_chapter(self) -> None:
        cb = TokenCircuitBreaker(
            chapter_budget=100.0,
            loop_threshold_tokens=999999,
        )
        for i in range(100):
            cb.check_and_record(chapter_id="ch1", tokens_used=10, cost=0.01)

        records = cb._records.get("ch1", [])
        self.assertLessEqual(len(records), cb.MAX_RECORDS_PER_CHAPTER)


class SecurityTests(unittest.TestCase):
    def test_access_token_contains_type_field(self) -> None:
        from core.security import create_access_token, decode_access_token
        token = create_access_token("user-123")
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-123")
        self.assertEqual(payload["type"], "access")

    def test_password_hash_verification(self) -> None:
        from core.security import get_password_hash, verify_password
        hashed = get_password_hash("my_secret_pass")
        self.assertTrue(verify_password("my_secret_pass", hashed))
        self.assertFalse(verify_password("wrong_pass", hashed))

    def test_refresh_token_generation_is_deterministic_hash(self) -> None:
        from core.security import generate_refresh_token_value
        t1 = generate_refresh_token_value()
        t2 = generate_refresh_token_value()
        self.assertNotEqual(t1, t2)
        self.assertEqual(len(t1), 64)

    def test_decode_access_token_rejects_refresh_type(self) -> None:
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from core.config import get_settings
        from core.security import decode_access_token
        settings = get_settings()
        payload = {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "refresh",
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with self.assertRaises(Exception) as ctx:
            decode_access_token(token)
        self.assertIn("invalid_token_type", str(ctx.exception))


class TransactionalContextManagerTests(unittest.TestCase):
    def test_transactional_commits_on_success(self) -> None:
        import asyncio
        from db.session import transactional
        from unittest.mock import AsyncMock

        async def run_test() -> None:
            mock_session = AsyncMock()
            async with transactional(mock_session) as session:
                self.assertIs(session, mock_session)
            mock_session.commit.assert_awaited_once()

        asyncio.run(run_test())

    def test_transactional_rollbacks_on_exception(self) -> None:
        import asyncio
        from db.session import transactional
        from core.errors import AppError
        from unittest.mock import AsyncMock

        async def run_test() -> None:
            mock_session = AsyncMock()
            with self.assertRaises(AppError):
                async with transactional(mock_session):
                    raise AppError(code="test", message="fail", status_code=400)
            mock_session.rollback.assert_awaited_once()
            mock_session.commit.assert_not_awaited()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
