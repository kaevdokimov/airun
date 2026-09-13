from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    create_access_token,
    require_bot_secret,
    validate_bot_telegram_header,
    verify_telegram_widget_auth,
)
from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models import User
from app.schemas import AuthTokenResponse, TelegramWebAuthRequest, UserCreate, UserResponse

router = APIRouter()


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
