from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_telegram_id
from app.api.v1.routes.common import get_user_by_telegram
from app.database import get_db
from app.schemas import SyncResponse
from app.services.garmin.sync import garmin_sync_service
from app.services.recommendations.service import recommendation_service

router = APIRouter(prefix="/sync")


@router.post("/trigger", response_model=SyncResponse)
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
