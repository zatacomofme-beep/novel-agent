from __future__ import annotations

import logging
import time
from typing import Optional

import redis.asyncio as redis

from core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ) -> None:
        settings = get_settings()
        self._redis_url = settings.redis_url
        self._requests_per_minute = requests_per_minute
        self._requests_per_hour = requests_per_hour
        self._burst_size = burst_size
        self._redis: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            if self._pool is None:
                self._pool = redis.ConnectionPool.from_url(
                    self._redis_url,
                    decode_responses=True,
                    max_connections=20,
                    retry_on_timeout=True,
                )
            self._redis = redis.Redis(connection_pool=self._pool)
        return self._redis

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

    async def __aenter__(self) -> RateLimiter:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _get_minute_key(self, identifier: str) -> str:
        minute = int(time.time() / 60)
        return f"rate_limit:minute:{identifier}:{minute}"

    def _get_hourly_key(self, identifier: str) -> str:
        hour = int(time.time() / 3600)
        return f"rate_limit:hourly:{identifier}:{hour}"

    async def check_rate_limit(
        self,
        identifier: str,
        cost: int = 1,
    ) -> tuple[bool, dict[str, int]]:
        r = await self._get_redis()

        minute_key = self._get_minute_key(identifier)
        hourly_key = self._get_hourly_key(identifier)

        current_minute = int(time.time() / 60)
        current_hour = int(time.time() / 3600)

        pipe = r.pipeline()

        pipe.incrby(minute_key, cost)
        pipe.expire(minute_key, 120)

        pipe.incrby(hourly_key, cost)
        pipe.expire(hourly_key, 7200)

        results = await pipe.execute()

        minute_count = results[0]
        hour_count = results[2]

        minute_limit = self._requests_per_minute
        hour_limit = self._requests_per_hour

        allowed = minute_count <= minute_limit and hour_count <= hour_limit

        remaining_minute = max(0, minute_limit - minute_count)
        remaining_hourly = max(0, hour_limit - hour_count)

        retry_after = 0
        if minute_count > minute_limit:
            retry_after = (current_minute + 1) * 60 - int(time.time())
        elif hour_count > hour_limit:
            retry_after = (current_hour + 1) * 3600 - int(time.time())

        return allowed, {
            "limit": minute_limit,
            "remaining": remaining_minute,
            "retry_after": retry_after,
            "hourly_limit": hour_limit,
            "hourly_remaining": remaining_hourly,
        }


_rate_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def close_rate_limiter() -> None:
    global _rate_limiter
    if _rate_limiter:
        await _rate_limiter.close()
        _rate_limiter = None
