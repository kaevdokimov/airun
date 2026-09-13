import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import GarminCredential, User
from app.services.garmin.exceptions import MFARequiredError
from app.services.garmin.unofficial import UnofficialGarminProvider
from app.services.security import get_credential_encryption

logger = logging.getLogger(__name__)

MFA_KEY_PREFIX = "garmin_mfa:"
MFA_TTL = 300


class GarminConnectService:
    def __init__(self) -> None:
        self.provider = UnofficialGarminProvider()
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        return self._redis

    def _encrypt_pending(self, payload: dict) -> str:
        return get_credential_encryption().encrypt(json.dumps(payload))

    def _decrypt_pending(self, encrypted: str) -> dict:
        return json.loads(get_credential_encryption().decrypt(encrypted))

    async def start_connect(
        self, db: AsyncSession, telegram_id: int, email: str, password: str
    ) -> dict:
        user = await self._get_or_create_user(db, telegram_id)
        mfa_pending = {"email": email, "password": password, "user_id": str(user.id)}

        redis = await self._get_redis()
        await redis.setex(
            f"{MFA_KEY_PREFIX}{telegram_id}",
            MFA_TTL,
            self._encrypt_pending(mfa_pending),
        )

        try:
            tokens = await self.provider.login(email, password)
            await self._save_credentials(db, user, email, tokens)
            await redis.delete(f"{MFA_KEY_PREFIX}{telegram_id}")
            return {"status": "connected", "message": "Garmin успешно подключён"}
        except MFARequiredError:
            return {"status": "mfa_required", "message": "Введите код MFA из приложения Garmin"}
        except Exception:
            await redis.delete(f"{MFA_KEY_PREFIX}{telegram_id}")
            raise

    async def submit_mfa(self, db: AsyncSession, telegram_id: int, mfa_code: str) -> dict:
        redis = await self._get_redis()
        pending_encrypted = await redis.get(f"{MFA_KEY_PREFIX}{telegram_id}")
        if not pending_encrypted:
            return {"status": "error", "message": "Сессия MFA истекла. Начните подключение заново."}

        pending = self._decrypt_pending(pending_encrypted)
        email = pending["email"]
        password = pending["password"]
        user_id = UUID(pending["user_id"])

        mfa_code_holder = {"code": mfa_code}

        def prompt_mfa() -> str:
            return mfa_code_holder["code"]

        try:
            tokens = await self.provider.login(email, password, prompt_mfa=prompt_mfa)
        except Exception:
            return {"status": "error", "message": "Ошибка MFA. Проверьте код и попробуйте снова."}

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        if user.telegram_id != telegram_id:
            return {"status": "error", "message": "Несоответствие сессии MFA"}
        await self._save_credentials(db, user, email, tokens)
        await redis.delete(f"{MFA_KEY_PREFIX}{telegram_id}")
        return {"status": "connected", "message": "Garmin успешно подключён"}

    async def disconnect(self, db: AsyncSession, telegram_id: int) -> None:
        result = await db.execute(
            select(User)
            .options(selectinload(User.garmin_credential))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user and user.garmin_credential:
            await db.delete(user.garmin_credential)

    async def get_status(self, db: AsyncSession, telegram_id: int) -> dict:
        result = await db.execute(
            select(User)
            .options(selectinload(User.garmin_credential))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.garmin_credential:
            return {"connected": False}
        cred = user.garmin_credential
        return {
            "connected": cred.is_active,
            "email": cred.garmin_email,
            "last_error": cred.last_error,
        }

    async def _save_credentials(
        self, db: AsyncSession, user: User, email: str, tokens: dict
    ) -> None:
        encrypted = get_credential_encryption().encrypt_tokens(tokens)
        if user.garmin_credential:
            user.garmin_credential.encrypted_tokens = encrypted
            user.garmin_credential.garmin_email = email
            user.garmin_credential.is_active = True
            user.garmin_credential.last_error = None
        else:
            db.add(
                GarminCredential(
                    user_id=user.id,
                    encrypted_tokens=encrypted,
                    garmin_email=email,
                    is_active=True,
                )
            )

    async def _get_or_create_user(self, db: AsyncSession, telegram_id: int) -> User:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)
            await db.flush()
        return user


garmin_connect_service = GarminConnectService()
