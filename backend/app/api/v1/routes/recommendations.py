from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_telegram_id
from app.api.v1.routes.common import get_user_by_telegram, recommendation_to_response
from app.database import get_db
from app.models import Recommendation
from app.schemas import GenerateRecommendationResponse, RecommendationResponse
from app.services.recommendations.service import recommendation_service

router = APIRouter(prefix="/recommendations")


@router.get("/latest", response_model=RecommendationResponse | None)
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
    return recommendation_to_response(rec)


@router.get("", response_model=list[RecommendationResponse])
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
    return [recommendation_to_response(r) for r in result.scalars().all()]


@router.post("/generate", response_model=GenerateRecommendationResponse)
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
    return GenerateRecommendationResponse(success=True, recommendation=recommendation_to_response(rec))
