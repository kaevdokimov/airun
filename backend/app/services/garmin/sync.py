import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Activity, DailySummary, User
from app.services.ai.cache import llm_recommendation_cache
from app.services.garmin.unofficial import UnofficialGarminProvider
from app.services.security import get_credential_encryption
from app.utils.timezone import user_today

logger = logging.getLogger(__name__)


class GarminSyncService:
    def __init__(self) -> None:
        self.provider = UnofficialGarminProvider()

    async def sync_user(self, db: AsyncSession, user_id: UUID) -> dict[str, int]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.garmin_credential))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.garmin_credential or not user.garmin_credential.is_active:
            return {"activities_synced": 0, "summaries_synced": 0}

        credential = user.garmin_credential
        try:
            tokens = get_credential_encryption().decrypt_tokens(credential.encrypted_tokens)
            client = await self.provider.login_with_tokens(tokens)
        except Exception as exc:
            credential.last_error = str(exc)
            credential.is_active = False
            await db.flush()
            logger.error("Garmin auth failed for user %s: %s", user_id, exc)
            raise

        activities_synced = await self._sync_activities(db, user, client)
        summaries_synced = await self._sync_daily_summaries(db, user, client)

        user.last_synced_at = datetime.now(timezone.utc)
        credential.last_error = None
        await db.flush()
        await llm_recommendation_cache.invalidate_user(user_id)

        return {"activities_synced": activities_synced, "summaries_synced": summaries_synced}

    async def _sync_activities(self, db: AsyncSession, user: User, client: Any) -> int:
        activities = await self.provider.get_activities(client, start=0, limit=50)
        garmin_ids = [act.get("activityId") for act in activities if act.get("activityId")]
        if not garmin_ids:
            return 0

        existing_result = await db.execute(
            select(Activity.garmin_activity_id).where(
                Activity.user_id == user.id,
                Activity.garmin_activity_id.in_(garmin_ids),
            )
        )
        existing_ids = set(existing_result.scalars().all())

        synced = 0
        max_activity_id = user.last_activity_id or 0

        for act in activities:
            garmin_id = act.get("activityId")
            if not garmin_id or garmin_id in existing_ids:
                continue

            activity_type = (act.get("activityType", {}) or {}).get("typeKey", "unknown")
            distance = act.get("distance") or act.get("sumDistance")
            duration = act.get("duration") or act.get("elapsedDuration")
            start_time = act.get("startTimeLocal") or act.get("startTimeGMT")

            if start_time:
                try:
                    started_at = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                except ValueError:
                    started_at = datetime.now(timezone.utc)
            else:
                started_at = datetime.now(timezone.utc)

            activity = Activity(
                user_id=user.id,
                garmin_activity_id=garmin_id,
                activity_type=activity_type,
                distance_m=float(distance) if distance else None,
                duration_sec=int(duration) if duration else None,
                metrics=act,
                started_at=started_at,
            )
            db.add(activity)
            synced += 1
            if garmin_id > max_activity_id:
                max_activity_id = garmin_id

        user.last_activity_id = max_activity_id
        return synced

    async def _sync_daily_summaries(self, db: AsyncSession, user: User, client: Any) -> int:
        today = user_today(user.timezone)
        synced = 0

        for offset in range(3):
            target_date = today - timedelta(days=offset)
            stats = await self.provider.get_daily_stats(client, target_date)
            sleep = await self.provider.get_sleep_data(client, target_date)
            hrv = await self.provider.get_hrv_data(client, target_date)

            if sleep:
                stats["sleep"] = sleep
            if hrv:
                stats["hrv"] = hrv

            if offset == 0:
                training = await self.provider.get_training_status(client)
                if training:
                    stats["training_status"] = training

            if not stats:
                continue

            result = await db.execute(
                select(DailySummary).where(
                    DailySummary.user_id == user.id,
                    DailySummary.summary_date == target_date,
                )
            )
            summary = result.scalar_one_or_none()
            if summary:
                summary.stats = stats
            else:
                db.add(DailySummary(user_id=user.id, summary_date=target_date, stats=stats))
            synced += 1

        return synced


garmin_sync_service = GarminSyncService()
