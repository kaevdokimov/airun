from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    create_access_token,
    get_authenticated_telegram_id,
    require_bot_secret,
    validate_bot_telegram_header,
    verify_telegram_widget_auth,
)
from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models import Activity, DailySummary, Goal, GoalStatus, Recommendation, User
from app.schemas import (
    ActivityResponse,
    AuthTokenResponse,
    DailySummaryResponse,
    GarminConnectRequest,
    GarminMfaRequest,
    GarminStatusResponse,
    GenerateRecommendationResponse,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    RecommendationResponse,
    SyncResponse,
    TelegramWebAuthRequest,
    UserCreate,
    UserResponse,
    WeekStatsResponse,
)
from app.services.garmin.connect import garmin_connect_service
from app.services.garmin.sync import garmin_sync_service
from app.services.recommendations.service import recommendation_service
from app.utils.timezone import user_today, user_week_ago_utc

router = APIRouter(prefix="/api/v1")


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


@router.post("/auth/telegram-web", response_model=AuthTokenResponse)
@limiter.limit("10/minute")
async def telegram_web_auth(
    request: Request,
    payload: TelegramWebAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram auth not configured")

    auth_data = {k: str(v) for k, v in payload.model_dump(exclude_none=True).items()}
    if not verify_telegram_widget_auth(auth_data, settings.telegram_bot_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram auth data")

    auth_date = int(auth_data.get("auth_date", 0))
    if datetime.now(timezone.utc).timestamp() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Telegram auth data expired")

    telegram_id = int(auth_data["id"])
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        await db.flush()

    token = create_access_token(telegram_id)
    return AuthTokenResponse(access_token=token, telegram_id=telegram_id)


@router.post("/users/telegram", response_model=UserResponse)
async def upsert_telegram_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_bot_secret),
    x_bot_telegram_id: str | None = Header(None, alias="X-Bot-Telegram-Id"),
):
    validate_bot_telegram_header(x_bot_telegram_id, payload.telegram_id)
    result = await db.execute(select(User).where(User.telegram_id == payload.telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.timezone = payload.timezone
    else:
        user = User(telegram_id=payload.telegram_id, timezone=payload.timezone)
        db.add(user)
        await db.flush()

    cred_result = await db.execute(
        select(User).options(selectinload(User.garmin_credential)).where(User.id == user.id)
    )
    user_with_cred = cred_result.scalar_one()
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        timezone=user.timezone,
        last_synced_at=user.last_synced_at,
        created_at=user.created_at,
        has_garmin=bool(user_with_cred.garmin_credential and user_with_cred.garmin_credential.is_active),
    )


@router.post("/garmin/connect")
async def garmin_connect(
    payload: GarminConnectRequest,
    db: AsyncSession = Depends(get_db),
    auth_telegram_id: int = Depends(get_authenticated_telegram_id),
):
    if auth_telegram_id != payload.telegram_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        return await garmin_connect_service.start_connect(
            db, payload.telegram_id, payload.email, payload.password
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось подключить Garmin") from None


@router.post("/garmin/mfa")
async def garmin_mfa(
    payload: GarminMfaRequest,
    db: AsyncSession = Depends(get_db),
    auth_telegram_id: int = Depends(get_authenticated_telegram_id),
):
    if auth_telegram_id != payload.telegram_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return await garmin_connect_service.submit_mfa(db, payload.telegram_id, payload.mfa_code)


@router.delete("/garmin/disconnect")
async def garmin_disconnect(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth_telegram_id: int = Depends(get_authenticated_telegram_id),
):
    if auth_telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await garmin_connect_service.disconnect(db, telegram_id)
    return {"status": "disconnected"}


@router.get("/garmin/status", response_model=GarminStatusResponse)
async def garmin_status(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    status = await garmin_connect_service.get_status(db, telegram_id)
    return GarminStatusResponse(**status)


@router.get("/goals", response_model=list[GoalResponse])
async def list_goals(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.user_id == user.id).order_by(Goal.race_date))
    return [goal_to_response(g, user.timezone) for g in result.scalars().all()]


@router.post("/goals", response_model=GoalResponse)
async def create_goal(
    payload: GoalCreate,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    if payload.race_date < user_today(user.timezone):
        raise HTTPException(status_code=400, detail="Дата забега должна быть в будущем")
    goal = Goal(
        user_id=user.id,
        distance=payload.distance,
        target_time_seconds=payload.target_time_seconds,
        race_date=payload.race_date,
    )
    db.add(goal)
    await db.flush()
    return goal_to_response(goal, user.timezone)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.flush()
    return goal_to_response(goal, user.timezone)


@router.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: UUID,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    return {"status": "deleted"}


@router.get("/stats/today", response_model=DailySummaryResponse | None)
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


@router.get("/stats/week", response_model=WeekStatsResponse)
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


@router.get("/recommendations/latest", response_model=RecommendationResponse | None)
async def latest_recommendation(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == user.id)
        .order_by(Recommendation.generated_at.desc())
        .limit(1)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        return None
    parsed = recommendation_service.parse_content(rec.content)
    return RecommendationResponse(
        id=rec.id,
        content=rec.content,
        parsed=parsed,
        context_snapshot=rec.context_snapshot,
        generated_at=rec.generated_at,
    )


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def list_recommendations(
    telegram_id: int = Query(...),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == user.id)
        .order_by(Recommendation.generated_at.desc())
        .limit(limit)
    )
    recs = result.scalars().all()
    return [
        RecommendationResponse(
            id=r.id,
            content=r.content,
            parsed=recommendation_service.parse_content(r.content),
            context_snapshot=r.context_snapshot,
            generated_at=r.generated_at,
        )
        for r in recs
    ]


@router.post("/recommendations/generate", response_model=GenerateRecommendationResponse)
async def generate_recommendation(
    telegram_id: int = Query(...),
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    try:
        rec = await recommendation_service.generate(db, user.id, force=force)
    except Exception:
        return GenerateRecommendationResponse(success=False, message="Ошибка генерации рекомендаций")
    if not rec:
        return GenerateRecommendationResponse(
            success=False,
            message="Нет активных целей или cooldown ещё не истёк",
        )
    parsed = recommendation_service.parse_content(rec.content)
    return GenerateRecommendationResponse(
        success=True,
        recommendation=RecommendationResponse(
            id=rec.id,
            content=rec.content,
            parsed=parsed,
            context_snapshot=rec.context_snapshot,
            generated_at=rec.generated_at,
        ),
    )


@router.post("/sync/trigger", response_model=SyncResponse)
async def trigger_sync(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    if not user.garmin_credential or not user.garmin_credential.is_active:
        return SyncResponse(success=False, message="Garmin не подключён")
    try:
        result = await garmin_sync_service.sync_user(db, user.id)
        activities_synced = result["activities_synced"]
        if await recommendation_service.should_auto_generate(db, user, activities_synced):
            await recommendation_service.generate(db, user.id, force=activities_synced > 0)
        return SyncResponse(
            success=True,
            activities_synced=activities_synced,
            summaries_synced=result["summaries_synced"],
            message="Синхронизация завершена",
        )
    except Exception:
        return SyncResponse(success=False, message="Ошибка синхронизации")
