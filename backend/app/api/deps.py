import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


def _jwt_secret() -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="JWT auth not configured")
    return settings.jwt_secret


def create_access_token(telegram_id: int) -> str:
    payload = {
        "sub": str(telegram_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def verify_telegram_widget_auth(auth_data: dict, bot_token: str) -> bool:
    """Verify Telegram Login Widget data per https://core.telegram.org/widgets/login"""
    received_hash = auth_data.get("hash")
    if not received_hash:
        return False
    check_data = {k: str(v) for k, v in auth_data.items() if k != "hash" and v is not None}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received_hash)


def parse_bot_telegram_id(x_bot_telegram_id: str | None) -> int:
    if not x_bot_telegram_id:
        raise HTTPException(status_code=403, detail="X-Bot-Telegram-Id header required")
    try:
        return int(x_bot_telegram_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Bot-Telegram-Id header") from exc


def validate_bot_telegram_header(x_bot_telegram_id: str | None, telegram_id: int) -> None:
    bot_telegram_id = parse_bot_telegram_id(x_bot_telegram_id)
    if bot_telegram_id != telegram_id:
        raise HTTPException(
            status_code=403,
            detail="X-Bot-Telegram-Id must match telegram_id",
        )


async def get_authenticated_telegram_id(
    telegram_id: int = Query(...),
    x_internal_bot_secret: str | None = Header(None, alias="X-Internal-Bot-Secret"),
    x_bot_telegram_id: str | None = Header(None, alias="X-Bot-Telegram-Id"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    settings = get_settings()

    if x_internal_bot_secret and hmac.compare_digest(
        x_internal_bot_secret, settings.internal_bot_secret
    ):
        validate_bot_telegram_header(x_bot_telegram_id, telegram_id)
        return telegram_id

    if credentials and credentials.credentials:
        token_telegram_id = decode_access_token(credentials.credentials)
        if token_telegram_id != telegram_id:
            raise HTTPException(status_code=403, detail="Token does not match telegram_id")
        return telegram_id

    raise HTTPException(status_code=401, detail="Authentication required")


async def require_bot_secret(
    x_internal_bot_secret: str | None = Header(None, alias="X-Internal-Bot-Secret"),
) -> None:
    settings = get_settings()
    if not x_internal_bot_secret or not hmac.compare_digest(
        x_internal_bot_secret, settings.internal_bot_secret
    ):
        raise HTTPException(status_code=401, detail="Bot authentication required")
