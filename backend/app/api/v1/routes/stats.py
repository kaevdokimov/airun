from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_telegram_id
from app.api.v1.routes.common import get_user_by_telegram
from app.database import get_db
from app.models import Activity, DailySummary
from app.schemas import ActivityResponse, DailySummaryResponse, WeekStatsResponse
from app.utils.timezone import user_today, user_week_ago_utc

router = APIRouter(prefix="/stats")


@router.get("/today", response_model=DailySummaryResponse | None)
async def stats_today(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    today = user_today(user.timezone)
    result = await db.execute(
        select(DailySummary).where(DailySummary.user_id == user.id, DailySummary.summary_date == today)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        return None
    return DailySummaryResponse(summary_date=summary.summary_date, stats=summary.stats)


@router.get("/week", response_model=WeekStatsResponse)
async def stats_week(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    week_ago = user_week_ago_utc(user.timezone)
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id, Activity.started_at >= week_ago)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    return WeekStatsResponse(
        total_distance_m=sum(a.distance_m or 0 for a in activities),
        total_duration_sec=sum(a.duration_sec or 0 for a in activities),
        activity_count=len(activities),
        activities=[ActivityResponse.model_validate(a) for a in activities],
    )
