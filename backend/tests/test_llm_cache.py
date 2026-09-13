from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import Goal, GoalDistance, GoalStatus, Recommendation, User
from app.schemas import RecommendationContent
from app.services.ai.cache import LLMRecommendationCache
from app.services.ai.prompts import PROMPT_VERSION
from app.services.recommendations.service import RecommendationService


@pytest.fixture
def cache_enabled(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_SECONDS", "3900")
    monkeypatch.setenv("RECOMMENDATION_COOLDOWN_HOURS", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _active_goal(user_id) -> Goal:
    return Goal(
        id=uuid4(),
        user_id=user_id,
        distance=GoalDistance.TEN_K,
        target_time_seconds=3600,
        race_date=datetime.now(timezone.utc).date() + timedelta(days=60),
        status=GoalStatus.ACTIVE,
    )


def _user(user_id, goal: Goal) -> User:
    user = User(
        id=user_id,
        telegram_id=111,
        timezone="Europe/Moscow",
        last_recommendation_at=None,
    )
    user.goals = [goal]
    return user


def _context_db_mocks(user: User, goal: Goal):
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    empty_scalars = MagicMock()
    empty_scalars.all.return_value = []
    empty_result = MagicMock()
    empty_result.scalars.return_value = empty_scalars

    goals_result = MagicMock()
    goals_scalars = MagicMock()
    goals_scalars.all.return_value = [goal]
    goals_result.scalars.return_value = goals_scalars

    return user_result, goals_result, empty_result


def test_build_key_includes_user_date_hash_and_version(cache_enabled):
    cache = LLMRecommendationCache()
    user_a = uuid4()
    user_b = uuid4()
    context_date = date(2026, 9, 13)

    key_a = cache.build_key(user_a, context_date, "prompt-one")
    key_b = cache.build_key(user_b, context_date, "prompt-one")
    key_prompt = cache.build_key(user_a, context_date, "prompt-two")
    key_date = cache.build_key(user_a, date(2026, 9, 14), "prompt-one")

    assert str(user_a) in key_a
    assert "2026-09-13" in key_a
    assert f"v{PROMPT_VERSION}" in key_a
    assert len(key_a.split(":")[-2]) == 32
    assert key_a != key_b
    assert key_a != key_prompt
    assert key_a != key_date


def test_effective_ttl_outlives_cooldown(cache_enabled, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_SECONDS", "900")
    monkeypatch.setenv("RECOMMENDATION_COOLDOWN_HOURS", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    cache = LLMRecommendationCache()
    assert cache.effective_ttl_seconds() == 3600 + 300


@pytest.mark.asyncio
async def test_cache_get_set_roundtrip(cache_enabled):
    cache = LLMRecommendationCache()
    user_id = uuid4()
    context_date = date(2026, 9, 13)
    prompt = "same prompt"
    content = RecommendationContent(
        summary="cached",
        today_recommendation="rest",
        week_plan=["Пн: отдых"],
        warnings=[],
        progress_to_goal="ok",
    )

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=content.model_dump_json(ensure_ascii=False))
    redis.setex = AsyncMock()
    cache._redis = redis

    await cache.set(user_id, context_date, prompt, content)
    redis.setex.assert_awaited_once()
    assert redis.setex.await_args.args[1] == cache.effective_ttl_seconds()

    got = await cache.get(user_id, context_date, prompt)
    assert got is not None
    assert got.summary == "cached"


@pytest.mark.asyncio
async def test_cache_isolates_users(cache_enabled):
    cache = LLMRecommendationCache()
    user_a = uuid4()
    user_b = uuid4()
    context_date = date(2026, 9, 13)
    prompt = "shared prompt text"
    content = RecommendationContent(summary="a", today_recommendation="run")

    store: dict[str, str] = {}

    redis = AsyncMock()

    async def _setex(key, ttl, value):
        store[key] = value

    async def _get(key):
        return store.get(key)

    redis.setex = AsyncMock(side_effect=_setex)
    redis.get = AsyncMock(side_effect=_get)
    cache._redis = redis

    await cache.set(user_a, context_date, prompt, content)
    assert await cache.get(user_a, context_date, prompt) is not None
    assert await cache.get(user_b, context_date, prompt) is None


@pytest.mark.asyncio
async def test_invalidate_user_unlinks_matching_keys(cache_enabled):
    cache = LLMRecommendationCache()
    user_id = uuid4()
    other_id = uuid4()
    keys = [
        cache.build_key(user_id, date(2026, 9, 13), "p1"),
        cache.build_key(user_id, date(2026, 9, 12), "p2"),
        cache.build_key(other_id, date(2026, 9, 13), "p1"),
    ]

    async def _scan_iter(match=None, count=100):
        for key in keys:
            if match and str(user_id) in match and str(user_id) in key:
                yield key

    redis = AsyncMock()
    redis.scan_iter = MagicMock(side_effect=lambda **kwargs: _scan_iter(**kwargs))
    redis.unlink = AsyncMock()
    cache._redis = redis

    await cache.invalidate_user(user_id)

    redis.unlink.assert_awaited_once()
    deleted = set(redis.unlink.await_args.args)
    assert keys[0] in deleted
    assert keys[1] in deleted
    assert keys[2] not in deleted


@pytest.mark.asyncio
async def test_generate_uses_cache_hit_reuses_latest_without_llm(cache_enabled):
    user_id = uuid4()
    goal = _active_goal(user_id)
    user = _user(user_id, goal)
    user.last_recommendation_at = datetime.now(timezone.utc) - timedelta(hours=2)

    cached = RecommendationContent(summary="from-cache", today_recommendation="easy")
    content = cached.model_dump_json(ensure_ascii=False)
    existing = Recommendation(
        id=uuid4(),
        user_id=user_id,
        goal_id=goal.id,
        content=content,
        context_snapshot={},
    )

    user_result, goals_result, empty_result = _context_db_mocks(user, goal)
    latest_result = MagicMock()
    latest_result.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[user_result, goals_result, empty_result, empty_result, latest_result]
    )
    db.add = MagicMock()
    db.flush = AsyncMock()
    llm = AsyncMock()

    with (
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.get",
            new_callable=AsyncMock,
            return_value=cached,
        ) as cache_get,
        patch(
            "app.services.recommendations.service.get_llm_provider",
            return_value=llm,
        ),
    ):
        service = RecommendationService(cooldown_hours=1)
        result = await service.generate(db, user_id, force=False)

    assert result is existing
    assert user.last_recommendation_at is not None
    db.add.assert_not_called()
    llm.generate_recommendation.assert_not_called()
    cache_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_force_bypasses_cache_and_calls_llm(cache_enabled):
    user_id = uuid4()
    goal = _active_goal(user_id)
    user = _user(user_id, goal)
    user.last_recommendation_at = datetime.now(timezone.utc)

    user_result, goals_result, empty_result = _context_db_mocks(user, goal)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[user_result, goals_result, empty_result, empty_result])
    db.add = MagicMock()
    db.flush = AsyncMock()

    parsed = RecommendationContent(summary="fresh", today_recommendation="run")
    llm = AsyncMock()
    llm.generate_recommendation = AsyncMock(return_value=parsed)

    with (
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.get",
            new_callable=AsyncMock,
            return_value=RecommendationContent(summary="stale", today_recommendation="rest"),
        ) as cache_get,
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.set",
            new_callable=AsyncMock,
        ) as cache_set,
        patch(
            "app.services.recommendations.service.get_llm_provider",
            return_value=llm,
        ),
    ):
        service = RecommendationService(cooldown_hours=24)
        result = await service.generate(db, user_id, force=True)

    assert result is not None
    assert "fresh" in result.content
    cache_get.assert_not_called()
    llm.generate_recommendation.assert_awaited_once()
    cache_set.assert_awaited_once()
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_cache_disabled_when_ttl_zero(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL_SECONDS", "0")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        cache = LLMRecommendationCache()
        redis = AsyncMock()
        cache._redis = redis
        content = RecommendationContent(summary="x", today_recommendation="y")
        await cache.set(uuid4(), date.today(), "p", content)
        assert await cache.get(uuid4(), date.today(), "p") is None
        redis.get.assert_not_called()
        redis.setex.assert_not_called()
        assert cache.effective_ttl_seconds() == 0
    finally:
        get_settings.cache_clear()
