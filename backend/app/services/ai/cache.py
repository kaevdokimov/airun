"""LLM recommendation response cache with per-user isolation."""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from uuid import UUID

import redis.asyncio as aioredis

from app.config import get_settings
from app.schemas import RecommendationContent
from app.services.ai.prompts import PROMPT_VERSION

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "llm:rec:"
# Keep cache alive past recommendation cooldown so repeated generate can reuse LLM output.
_CACHE_TTL_COOLDOWN_BUFFER_SECONDS = 300
_PROMPT_HASH_HEX_LEN = 32


class LLMRecommendationCache:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        return self._redis

    def effective_ttl_seconds(self) -> int:
        """Return TTL to use, or 0 when cache is disabled.

        Configured TTL is raised to at least cooldown + buffer so a generate after
        cooldown can still hit the cache when context is unchanged.
        """
        settings = get_settings()
        configured = settings.llm_cache_ttl_seconds
        if configured <= 0:
            return 0
        cooldown_seconds = max(0, settings.recommendation_cooldown_hours) * 3600
        return max(configured, cooldown_seconds + _CACHE_TTL_COOLDOWN_BUFFER_SECONDS)

    def build_key(self, user_id: UUID, context_date: date, prompt: str) -> str:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:_PROMPT_HASH_HEX_LEN]
        return (
            f"{CACHE_KEY_PREFIX}{user_id}:{context_date.isoformat()}:"
            f"{prompt_hash}:v{PROMPT_VERSION}"
        )

    def _user_pattern(self, user_id: UUID) -> str:
        return f"{CACHE_KEY_PREFIX}{user_id}:*"

    async def get(
        self,
        user_id: UUID,
        context_date: date,
        prompt: str,
    ) -> RecommendationContent | None:
        if self.effective_ttl_seconds() <= 0:
            return None
        key = self.build_key(user_id, context_date, prompt)
        try:
            redis = await self._get_redis()
            raw = await redis.get(key)
        except Exception as exc:
            logger.warning("LLM cache get failed for user %s: %s", user_id, exc)
            return None
        if not raw:
            return None
        try:
            return RecommendationContent.model_validate_json(raw)
        except Exception:
            logger.warning("LLM cache entry invalid for key %s", key)
            return None

    async def set(
        self,
        user_id: UUID,
        context_date: date,
        prompt: str,
        content: RecommendationContent,
    ) -> None:
        ttl = self.effective_ttl_seconds()
        if ttl <= 0:
            return
        key = self.build_key(user_id, context_date, prompt)
        try:
            redis = await self._get_redis()
            await redis.setex(key, ttl, content.model_dump_json(ensure_ascii=False))
        except Exception as exc:
            logger.warning("LLM cache set failed for user %s: %s", user_id, exc)

    async def invalidate_user(self, user_id: UUID) -> None:
        if self.effective_ttl_seconds() <= 0:
            return
        pattern = self._user_pattern(user_id)
        try:
            redis = await self._get_redis()
            keys: list[str] = []
            async for key in redis.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                await redis.unlink(*keys)
        except Exception as exc:
            logger.warning("LLM cache invalidate failed for user %s: %s", user_id, exc)


llm_recommendation_cache = LLMRecommendationCache()
