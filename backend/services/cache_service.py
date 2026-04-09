from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import redis.asyncio as redis

from core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    ttl: int = 300
    key_prefix: str = "cache"
    invalidate_on: list[str] | None = None


CACHE_CONFIGS: dict[str, CacheConfig] = {
    "story_bible": CacheConfig(
        ttl=300,
        key_prefix="sb",
        invalidate_on=["story_bible_updated"],
    ),
    "chapter_draft": CacheConfig(
        ttl=600,
        key_prefix="draft",
        invalidate_on=["chapter_saved", "generation_completed"],
    ),
    "project_stats": CacheConfig(
        ttl=3600,
        key_prefix="stats",
        invalidate_on=["chapter_created", "chapter_deleted"],
    ),
    "user_session": CacheConfig(
        ttl=1800,
        key_prefix="session",
        invalidate_on=["logout"],
    ),
    "character_profile": CacheConfig(
        ttl=600,
        key_prefix="char",
        invalidate_on=["character_updated", "chapter_completed"],
    ),
}


class RedisCacheService:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            settings = get_settings()
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as exc:
            logger.debug("Cache GET failed for key %s: %s", key, exc)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        try:
            client = await self.get_client()
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if ttl:
                await client.setex(key, ttl, value)
            else:
                await client.set(key, value)
        except Exception as exc:
            logger.debug("Cache SET failed for key %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        try:
            client = await self.get_client()
            await client.delete(key)
        except Exception as exc:
            logger.debug("Cache DELETE failed for key %s: %s", key, exc)

    async def delete_pattern(self, pattern: str) -> None:
        try:
            client = await self.get_client()
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.debug("Cache DELETE_PATTERN failed for pattern %s: %s", pattern, exc)

    def build_key(self, cache_type: str, *parts: str) -> str:
        config = CACHE_CONFIGS.get(cache_type, CacheConfig())
        return f"{config.key_prefix}:{':'.join(parts)}"

    async def get_cached(
        self,
        cache_type: str,
        *key_parts: str,
    ) -> Optional[Any]:
        config = CACHE_CONFIGS.get(cache_type, CacheConfig())
        key = self.build_key(cache_type, *key_parts)
        return await self.get(key)

    async def set_cached(
        self,
        cache_type: str,
        value: Any,
        *key_parts: str,
    ) -> None:
        config = CACHE_CONFIGS.get(cache_type, CacheConfig())
        key = self.build_key(cache_type, *key_parts)
        await self.set(key, value, ttl=config.ttl)

    async def invalidate_cache_type(self, cache_type: str, *key_parts: str) -> None:
        if key_parts:
            key = self.build_key(cache_type, *key_parts)
            await self.delete(key)
        else:
            config = CACHE_CONFIGS.get(cache_type, CacheConfig())
            pattern = f"{config.key_prefix}:*"
            await self.delete_pattern(pattern)

    async def invalidate_project_caches(self, project_id: str) -> None:
        client = await self.get_client()
        patterns = [f"{cfg.key_prefix}:{project_id}:*" for cfg in CACHE_CONFIGS.values()]
        for pattern in patterns:
            await self.delete_pattern(pattern)


cache_service = RedisCacheService()
