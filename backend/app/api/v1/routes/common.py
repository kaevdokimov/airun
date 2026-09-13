from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Goal, User
from app.schemas import GoalResponse, RecommendationResponse
from app.services.recommendations.service import recommendation_service
from app.utils.timezone import user_today


async def get_user_by_telegram(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.garmin_credential))
        .where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def goal_to_response(goal: Goal, timezone_name: str = "Europe/Moscow") -> GoalResponse:
    days = (goal.race_date - user_today(timezone_name)).days
    return GoalResponse(
        id=goal.id,
        distance=goal.distance,
        target_time_seconds=goal.target_time_seconds,
        race_date=goal.race_date,
        status=goal.status,
        days_until_race=days,
    )


def recommendation_to_response(rec) -> RecommendationResponse:
    return RecommendationResponse(
        id=rec.id,
        content=rec.content,
        parsed=recommendation_service.parse_content(rec.content),
        context_snapshot=rec.context_snapshot,
        generated_at=rec.generated_at,
    )
