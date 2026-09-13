from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_telegram_id
from app.database import get_db
from app.schemas import GarminConnectRequest, GarminMfaRequest, GarminStatusResponse
from app.services.garmin.connect import garmin_connect_service

router = APIRouter(prefix="/garmin")


@router.post("/connect")
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


@router.post("/mfa")
async def garmin_mfa(
    payload: GarminMfaRequest,
    db: AsyncSession = Depends(get_db),
    auth_telegram_id: int = Depends(get_authenticated_telegram_id),
):
    if auth_telegram_id != payload.telegram_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return await garmin_connect_service.submit_mfa(db, payload.telegram_id, payload.mfa_code)


@router.delete("/disconnect")
async def garmin_disconnect(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    auth_telegram_id: int = Depends(get_authenticated_telegram_id),
):
    if auth_telegram_id != telegram_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await garmin_connect_service.disconnect(db, telegram_id)
    return {"status": "disconnected"}


@router.get("/status", response_model=GarminStatusResponse)
async def garmin_status(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    status = await garmin_connect_service.get_status(db, telegram_id)
    return GarminStatusResponse(**status)
