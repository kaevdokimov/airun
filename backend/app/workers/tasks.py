import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import exists, select
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import async_session_factory
from app.models import GarminCredential, Goal, GoalStatus, User
from app.services.garmin.sync import garmin_sync_service
from app.services.recommendations.service import recommendation_service

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery("airun", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-all-users": {
            "task": "app.workers.tasks.sync_all_users",
            "schedule": crontab(minute=f"*/{max(settings.sync_interval_minutes, 1)}"),
        },
        "morning-recommendations": {
            "task": "app.workers.tasks.generate_morning_digests",
            "schedule": crontab(minute=0),
        },
        "race-reminders": {
            "task": "app.workers.tasks.send_race_reminders",
            "schedule": crontab(minute=0),
        },
    },
)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


def run_async(coro):
    return asyncio.run(coro)


async def _sync_user(db, user_id: UUID) -> dict:
    result = await garmin_sync_service.sync_user(db, user_id)
    await db.commit()
    return result


async def _generate_recommendation(db, user_id: UUID, force: bool = False):
    rec = await recommendation_service.generate(db, user_id, force=force)
    await db.commit()
    return rec


async def _should_generate_after_sync(db, user_id: UUID, new_activities: int) -> bool:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    return await recommendation_service.should_auto_generate(db, user, new_activities)


async def _sync_all_users_async():
    async with async_session_factory() as db:
        result = await db.execute(
            select(User)
            .join(GarminCredential, User.id == GarminCredential.user_id)
            .where(GarminCredential.is_active.is_(True))
        )
        users = result.scalars().all()

    for user in users:
        try:
            async with async_session_factory() as db:
                try:
                    sync_result = await _sync_user(db, user.id)
                except Exception:
                    await db.rollback()
                    raise
                activities_synced = sync_result.get("activities_synced", 0)

            async with async_session_factory() as db:
                try:
                    if await _should_generate_after_sync(db, user.id, activities_synced):
                        await _generate_recommendation(db, user.id, force=activities_synced > 0)
                        if activities_synced > 0:
                            _notify_telegram(user.telegram_id, "new_activity", user.id)
                except Exception:
                    await db.rollback()
                    raise
        except Exception as exc:
            logger.error("Sync failed for user %s: %s", user.id, exc)


async def _generate_morning_digests_async():
    now_utc = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        has_garmin = exists().where(
            GarminCredential.user_id == User.id,
            GarminCredential.is_active.is_(True),
        )
        has_goals = exists().where(
            Goal.user_id == User.id,
            Goal.status == GoalStatus.ACTIVE,
        )
        result = await db.execute(select(User).where(has_garmin | has_goals))
        users = result.scalars().all()

    for user in users:
        try:
            tz = ZoneInfo(user.timezone)
            if now_utc.astimezone(tz).hour != 8:
                continue
            async with async_session_factory() as db:
                try:
                    rec = await _generate_recommendation(db, user.id, force=True)
                except Exception:
                    await db.rollback()
                    raise
                if rec:
                    _notify_telegram(user.telegram_id, "morning_digest", user.id)
        except Exception as exc:
            logger.error("Morning digest failed for user %s: %s", user.id, exc)


async def _send_race_reminders_async():
    now_utc = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        result = await db.execute(
            select(Goal)
            .options(joinedload(Goal.user))
            .where(Goal.status == GoalStatus.ACTIVE)
        )
        goals = result.scalars().unique().all()

    for goal in goals:
        if not goal.user:
            continue
        try:
            tz = ZoneInfo(goal.user.timezone)
            if now_utc.astimezone(tz).hour != 7:
                continue
            today = now_utc.astimezone(tz).date()
            days_left = (goal.race_date - today).days
            if days_left in (7, 3, 1):
                _notify_telegram(goal.user.telegram_id, f"race_reminder_{days_left}", goal.id)
        except Exception as exc:
            logger.error("Race reminder failed for goal %s: %s", goal.id, exc)


@celery_app.task(name="app.workers.tasks.sync_all_users")
def sync_all_users():
    run_async(_sync_all_users_async())


@celery_app.task(name="app.workers.tasks.generate_morning_digests")
def generate_morning_digests():
    run_async(_generate_morning_digests_async())


@celery_app.task(name="app.workers.tasks.send_race_reminders")
def send_race_reminders():
    run_async(_send_race_reminders_async())


def _notify_telegram(telegram_id: int, event_type: str, reference_id):
    r = _get_redis()
    r.publish(
        "telegram_notifications",
        json.dumps({"telegram_id": telegram_id, "event": event_type, "ref": str(reference_id)}),
    )
