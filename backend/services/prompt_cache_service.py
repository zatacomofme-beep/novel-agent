from __future__ import annotations

import hashlib
from typing import Any

from core.config import get_settings


class PromptCacheService:
    DEFAULT_TTL = 3600

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = getattr(settings, "cache_service_enabled", True)
        self._redis_client: Any | None = None
        self._memory_cache: dict[str, tuple[str, float]] = {}

    async def _get_redis(self) -> Any | None:
        if not self._enabled:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis.asyncio as redis
            settings = get_settings()
            self._redis_client = redis.Redis(
                host=getattr(settings, "redis_host", "localhost"),
                port=getattr(settings, "redis_port", 6379),
                db=getattr(settings, "redis_db", 0),
                decode_responses=True,
            )
            await self._redis_client.ping()
            return self._redis_client
        except Exception:
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
    ) -> str | None:
        if not self._enabled:
            return None
        key = self._make_prompt_key(prefix, prompt, system_prompt)

        redis_client = await self._get_redis()
        if redis_client:
            try:
                result = await redis_client.get(key)
                if result:
                    return result
            except Exception:
                pass

        cached = self._memory_cache.get(key)
        if cached:
            content, expiry = cached
            import time
            if time.time() < expiry:
                return content
            del self._memory_cache[key]
        return None

    async def set(
        self,
        prefix: str,
        prompt: str,
        system_prompt: str | None,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        if not self._enabled:
            return False
        key = self._make_prompt_key(prefix, prompt, system_prompt)
        ttl = ttl or self.DEFAULT_TTL

        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.setex(key, ttl, content)
                return True
            except Exception:
                pass

        import time
        self._memory_cache[key] = (content, time.time() + ttl)
        return True

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
            except Exception:
                pass

        to_delete = [k for k in self._memory_cache if pattern in k]
        for k in to_delete:
            del self._memory_cache[k]
            count += 1
        return count

    async def clear(self) -> None:
        self._memory_cache.clear()
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.flushdb()
            except Exception:
                pass


prompt_cache_service = PromptCacheService()
