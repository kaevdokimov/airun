from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import Activity, DailySummary, GarminCredential, User
from app.services.garmin.sync import GarminSyncService
from app.services.security import get_credential_encryption


async def _create_user_with_credential(db_session, *, active: bool = True) -> User:
    user = User(telegram_id=42_001, timezone="Europe/Moscow")
    db_session.add(user)
    await db_session.flush()

    encrypted = get_credential_encryption().encrypt_tokens({"oauth_token": "tok"})
    credential = GarminCredential(
        user_id=user.id,
        encrypted_tokens=encrypted,
        garmin_email="runner@example.com",
        is_active=active,
    )
    db_session.add(credential)
    await db_session.flush()
    return user


def _mock_provider(activities: list[dict] | None = None) -> AsyncMock:
    provider = AsyncMock()
    provider.login_with_tokens = AsyncMock(return_value=MagicMock(name="garmin-client"))
    provider.get_activities = AsyncMock(
        return_value=activities
        if activities is not None
        else [
            {
                "activityId": 1001,
                "activityType": {"typeKey": "running"},
                "distance": 5000.0,
                "duration": 1800,
                "startTimeGMT": "2026-09-10T07:00:00Z",
            }
        ]
    )
    provider.get_daily_stats = AsyncMock(return_value={"totalSteps": 8000})
    provider.get_sleep_data = AsyncMock(return_value={"sleepTimeSeconds": 25000})
    provider.get_hrv_data = AsyncMock(return_value={"lastNightAvg": 55})
    provider.get_training_status = AsyncMock(return_value={"status": "productive"})
    return provider


@pytest.mark.asyncio
async def test_sync_user_without_credential_returns_zeros(db_session):
    user = User(telegram_id=42_002, timezone="Europe/Moscow")
    db_session.add(user)
    await db_session.flush()

    service = GarminSyncService()
    result = await service.sync_user(db_session, user.id)

    assert result == {"activities_synced": 0, "summaries_synced": 0}


@pytest.mark.asyncio
async def test_sync_user_inserts_activity_and_summaries(auth_env, db_session):
    user = await _create_user_with_credential(db_session)
    service = GarminSyncService()
    service.provider = _mock_provider()

    with patch(
        "app.services.garmin.sync.llm_recommendation_cache.invalidate_user",
        new_callable=AsyncMock,
    ) as invalidate:
        result = await service.sync_user(db_session, user.id)

    assert result["activities_synced"] == 1
    assert result["summaries_synced"] == 3
    invalidate.assert_awaited_once_with(user.id)

    activities = (
        await db_session.execute(select(Activity).where(Activity.user_id == user.id))
    ).scalars().all()
    assert len(activities) == 1
    assert activities[0].garmin_activity_id == 1001

    await db_session.refresh(user)
    assert user.last_activity_id == 1001
    assert user.last_synced_at is not None

    summaries = (
        await db_session.execute(select(DailySummary).where(DailySummary.user_id == user.id))
    ).scalars().all()
    assert len(summaries) == 3


@pytest.mark.asyncio
async def test_sync_user_skips_duplicate_activity(auth_env, db_session):
    user = await _create_user_with_credential(db_session)
    db_session.add(
        Activity(
            user_id=user.id,
            garmin_activity_id=1001,
            activity_type="running",
            distance_m=5000.0,
            duration_sec=1800,
            metrics={},
            started_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()

    service = GarminSyncService()
    service.provider = _mock_provider()

    with patch(
        "app.services.garmin.sync.llm_recommendation_cache.invalidate_user",
        new_callable=AsyncMock,
    ):
        result = await service.sync_user(db_session, user.id)

    assert result["activities_synced"] == 0


@pytest.mark.asyncio
async def test_sync_user_auth_failure_deactivates_credential(auth_env, db_session):
    user = await _create_user_with_credential(db_session)
    service = GarminSyncService()
    provider = _mock_provider()
    provider.login_with_tokens = AsyncMock(side_effect=RuntimeError("token expired"))
    service.provider = provider

    with pytest.raises(RuntimeError, match="token expired"):
        await service.sync_user(db_session, user.id)

    credential = (
        await db_session.execute(
            select(GarminCredential).where(GarminCredential.user_id == user.id)
        )
    ).scalar_one()
    assert credential.is_active is False
    assert "token expired" in (credential.last_error or "")
