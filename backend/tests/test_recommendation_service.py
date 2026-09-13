from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import Goal, GoalDistance, GoalStatus, Recommendation, User
from app.schemas import RecommendationContent
from app.services.recommendations.service import RecommendationService


def _user(**kwargs) -> User:
    defaults = {
        "id": uuid4(),
        "telegram_id": 111,
        "timezone": "Europe/Moscow",
        "last_recommendation_at": None,
        "goals": [],
    }
    defaults.update(kwargs)
    user = User(
        id=defaults["id"],
        telegram_id=defaults["telegram_id"],
        timezone=defaults["timezone"],
        last_recommendation_at=defaults["last_recommendation_at"],
    )
    user.goals = defaults["goals"]
    return user


def _active_goal(user_id) -> Goal:
    return Goal(
        id=uuid4(),
        user_id=user_id,
        distance=GoalDistance.TEN_K,
        target_time_seconds=3600,
        race_date=datetime.now(timezone.utc).date() + timedelta(days=60),
        status=GoalStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_should_auto_generate_on_new_activities():
    service = RecommendationService(cooldown_hours=1)
    user = _user(last_recommendation_at=datetime.now(timezone.utc))
    assert await service.should_auto_generate(AsyncMock(), user, new_activities=1) is True


@pytest.mark.asyncio
async def test_should_auto_generate_when_never_generated():
    service = RecommendationService(cooldown_hours=1)
    user = _user(last_recommendation_at=None)
    assert await service.should_auto_generate(AsyncMock(), user, new_activities=0) is True


@pytest.mark.asyncio
async def test_should_auto_generate_respects_cooldown():
    service = RecommendationService(cooldown_hours=2)
    user = _user(last_recommendation_at=datetime.now(timezone.utc) - timedelta(minutes=30))
    assert await service.should_auto_generate(AsyncMock(), user, new_activities=0) is False


@pytest.mark.asyncio
async def test_should_auto_generate_after_cooldown():
    service = RecommendationService(cooldown_hours=1)
    user = _user(last_recommendation_at=datetime.now(timezone.utc) - timedelta(hours=2))
    assert await service.should_auto_generate(AsyncMock(), user, new_activities=0) is True


@pytest.mark.asyncio
async def test_generate_returns_none_without_goals():
    service = RecommendationService(cooldown_hours=1)
    user = _user(goals=[])

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=user_result)

    result = await service.generate(db, user.id, force=True)
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_none_during_cooldown():
    service = RecommendationService(cooldown_hours=1)
    user = _user(
        last_recommendation_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        goals=[_active_goal(uuid4())],
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=user_result)

    result = await service.generate(db, user.id, force=False)
    assert result is None


@pytest.mark.asyncio
async def test_generate_creates_recommendation_with_mocked_llm():
    service = RecommendationService(cooldown_hours=1)
    user_id = uuid4()
    goal = _active_goal(user_id)
    user = _user(id=user_id, goals=[goal], last_recommendation_at=None)

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

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[user_result, goals_result, empty_result, empty_result])
    db.add = MagicMock()
    db.flush = AsyncMock()

    parsed = RecommendationContent(
        summary="Лёгкая неделя",
        today_recommendation="Восстановительный бег 5 км",
        week_plan=["Пн: отдых", "Вт: 8 км"],
        warnings=[],
        progress_to_goal="В графике",
    )
    llm = AsyncMock()
    llm.generate_recommendation = AsyncMock(return_value=parsed)

    with (
        patch("app.services.recommendations.service.get_llm_provider", return_value=llm),
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.set",
            new_callable=AsyncMock,
        ),
    ):
        result = await service.generate(db, user_id, force=True)

    assert result is not None
    assert isinstance(result, Recommendation)
    assert result.user_id == user_id
    assert result.goal_id == goal.id
    assert "Лёгкая неделя" in result.content
    assert user.last_recommendation_at is not None
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    llm.generate_recommendation.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_force_bypasses_cooldown():
    service = RecommendationService(cooldown_hours=24)
    user_id = uuid4()
    goal = _active_goal(user_id)
    user = _user(
        id=user_id,
        goals=[goal],
        last_recommendation_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

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

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[user_result, goals_result, empty_result, empty_result])
    db.add = MagicMock()
    db.flush = AsyncMock()

    parsed = RecommendationContent(summary="ok", today_recommendation="run")
    llm = AsyncMock()
    llm.generate_recommendation = AsyncMock(return_value=parsed)

    with (
        patch("app.services.recommendations.service.get_llm_provider", return_value=llm),
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.recommendations.service.llm_recommendation_cache.set",
            new_callable=AsyncMock,
        ),
    ):
        result = await service.generate(db, user_id, force=True)

    assert result is not None
