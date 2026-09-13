import logging
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Activity, DailySummary, Goal, GoalStatus, Recommendation, User
from app.schemas import RecommendationContent
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import build_recommendation_prompt
from app.utils.timezone import user_today

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, cooldown_hours: int = 1) -> None:
        self.cooldown_hours = cooldown_hours

    async def should_auto_generate(self, db: AsyncSession, user: User, new_activities: int) -> bool:
        if new_activities > 0:
            return True
        if not user.last_recommendation_at:
            return True
        cooldown = timedelta(hours=self.cooldown_hours)
        return datetime.now(timezone.utc) - user.last_recommendation_at >= cooldown

    async def generate(
        self,
        db: AsyncSession,
        user_id: UUID,
        force: bool = False,
    ) -> Recommendation | None:
        result = await db.execute(
            select(User)
            .options(selectinload(User.goals))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        if not force and user.last_recommendation_at:
            cooldown = timedelta(hours=self.cooldown_hours)
            if datetime.now(timezone.utc) - user.last_recommendation_at < cooldown:
                return None

        context = await self._build_context(db, user)
        if not context.get("goals"):
            return None

        llm = get_llm_provider()
        prompt = build_recommendation_prompt(context)

        try:
            parsed = await llm.generate_recommendation(prompt)
        except Exception as exc:
            logger.error("LLM generation failed for user %s: %s", user_id, exc)
            raise

        content = parsed.model_dump_json(ensure_ascii=False)
        primary_goal = next((g for g in user.goals if g.status == GoalStatus.ACTIVE), None)

        recommendation = Recommendation(
            user_id=user.id,
            goal_id=primary_goal.id if primary_goal else None,
            content=content,
            context_snapshot=context,
        )
        db.add(recommendation)
        user.last_recommendation_at = datetime.now(timezone.utc)
        await db.flush()
        return recommendation

    async def _build_context(self, db: AsyncSession, user: User) -> dict:
        today = user_today(user.timezone)
        week_ago = today - timedelta(days=28)
        week_ago_dt = datetime.combine(week_ago, time.min, tzinfo=ZoneInfo(user.timezone)).astimezone(
            timezone.utc
        )
        week_start = today - timedelta(days=7)

        goals_result = await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.status == GoalStatus.ACTIVE)
        )
        goals = goals_result.scalars().all()

        activities_result = await db.execute(
            select(Activity)
            .where(Activity.user_id == user.id, Activity.started_at >= week_ago_dt)
            .order_by(Activity.started_at.desc())
            .limit(50)
        )
        activities = activities_result.scalars().all()

        summaries_result = await db.execute(
            select(DailySummary)
            .where(DailySummary.user_id == user.id, DailySummary.summary_date >= week_ago)
            .order_by(DailySummary.summary_date.desc())
            .limit(14)
        )
        summaries = summaries_result.scalars().all()

        weekly_distance = sum(
            a.distance_m or 0
            for a in activities
            if a.started_at.astimezone(ZoneInfo(user.timezone)).date() >= week_start
        )

        return {
            "user_timezone": user.timezone,
            "goals": [
                {
                    "distance": g.distance.value,
                    "target_time_seconds": g.target_time_seconds,
                    "race_date": g.race_date.isoformat(),
                    "days_until_race": (g.race_date - today).days,
                }
                for g in goals
            ],
            "activities": [
                {
                    "type": a.activity_type,
                    "distance_m": a.distance_m,
                    "duration_sec": a.duration_sec,
                    "pace_min_per_km": round((a.duration_sec or 0) / 60 / (a.distance_m / 1000), 2)
                    if a.distance_m and a.distance_m > 0
                    else None,
                    "started_at": a.started_at.isoformat(),
                }
                for a in activities
            ],
            "weekly_distance_km": round(weekly_distance / 1000, 2),
            "daily_summaries": [
                {"date": s.summary_date.isoformat(), "stats": s.stats} for s in summaries[:7]
            ],
        }

    def parse_content(self, content: str) -> RecommendationContent | None:
        try:
            return RecommendationContent.model_validate_json(content)
        except Exception:
            return None


recommendation_service = RecommendationService(cooldown_hours=get_settings().recommendation_cooldown_hours)
