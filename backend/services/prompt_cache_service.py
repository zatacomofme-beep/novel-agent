from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

import redis.asyncio as redis

from core.config import get_settings
from core.degraded_response import DegradedResponse

if TYPE_CHECKING:
    from core.types_redis import RedisClientProtocol


class PromptCacheService:
    DEFAULT_TTL = 3600
    MAX_MEMORY_ENTRIES = 500

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = getattr(settings, "cache_service_enabled", True)
        self._redis_client: RedisClientProtocol | None = None
        self._memory_cache: dict[str, tuple[str, float]] = {}
        self._memory_access_order: list[str] = []

    async def _get_redis(self) -> RedisClientProtocol | None:
        if not self._enabled:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            settings = get_settings()
            self._redis_client = redis.Redis(
                host=getattr(settings, "redis_host", "localhost"),
                port=getattr(settings, "redis_port", 6379),
                db=getattr(settings, "redis_db", 0),
                decode_responses=True,
            )
            await self._redis_client.ping()
            return self._redis_client
        except (redis.ConnectionError, redis.TimeoutError):
            self._redis_client = None
            return None

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def _make_prompt_key(self, prefix: str, prompt: str, system: str | None) -> str:
        combined = f"{prefix}:{system or ''}:{prompt}"
        return f"prompt:{self._hash_key(combined)}"

    async def get(
        self,
        prefix: str,
        prompt: str,
        system_prompt: str | None = None,
    ) -> DegradedResponse[str]:
        if not self._enabled:
            return DegradedResponse.empty(source="prompt_cache", reason="disabled")
        key = self._make_prompt_key(prefix, prompt, system_prompt)

        redis_client = await self._get_redis()
        if redis_client:
            try:
                result = await redis_client.get(key)
                if result:
                    return DegradedResponse.ok(result, source="prompt_cache:redis")
            except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
                pass

        cached = self._memory_cache.get(key)
        if cached:
            content, expiry = cached
            import time
            if time.time() < expiry:
                self._touch_lru(key)
                return DegradedResponse.ok(content, source="prompt_cache:memory")
            del self._memory_cache[key]
            try:
                self._memory_access_order.remove(key)
            except ValueError:
                pass
        return DegradedResponse.empty(source="prompt_cache", reason="miss")

    async def set(
        self,
        prefix: str,
        prompt: str,
        system_prompt: str | None,
        content: str,
        ttl: int | None = None,
    ) -> DegradedResponse[bool]:
        if not self._enabled:
            return DegradedResponse.fallback(False, source="prompt_cache", reason="disabled")
        key = self._make_prompt_key(prefix, prompt, system_prompt)
        ttl = ttl or self.DEFAULT_TTL

        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.setex(key, ttl, content)
                return DegradedResponse.ok(True, source="prompt_cache:redis")
            except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
                pass

        self._evict_if_needed()
        self._memory_cache[key] = (content, time.time() + ttl)
        self._touch_lru(key)
        return DegradedResponse.ok(True, source="prompt_cache:memory")

    async def invalidate(self, pattern: str) -> int:
        count = 0
        redis_client = await self._get_redis()
        if redis_client:
            try:
                keys = []
                async for key in redis_client.scan_iter(match=f"prompt:*{pattern}*"):
                    keys.append(key)
                if keys:
                    count += await redis_client.delete(*keys)
            except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
                pass

        to_delete = [k for k in self._memory_cache if pattern in k]
        for k in to_delete:
            del self._memory_cache[k]
            count += 1
        return count

    async def clear(self) -> None:
        self._memory_cache.clear()
        self._memory_access_order.clear()
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.flushdb()
            except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
                pass

    def _touch_lru(self, key: str) -> None:
        try:
            self._memory_access_order.remove(key)
        except ValueError:
            pass
        self._memory_access_order.append(key)

    def _evict_if_needed(self) -> None:
        while len(self._memory_cache) >= self.MAX_MEMORY_ENTRIES:
            oldest = self._memory_access_order[0]
            self._memory_access_order.pop(0)
            self._memory_cache.pop(oldest, None)


prompt_cache_service = PromptCacheService()
