import asyncio
import logging
from datetime import date
from typing import Any, Callable

from garminconnect import Garmin

from app.services.garmin.exceptions import MFARequiredError
from app.services.garmin.provider import GarminDataProvider

logger = logging.getLogger(__name__)

MFA_MARKERS = ("mfa", "verification", "two-factor", "two factor", "one-time", "otp")


class UnofficialGarminProvider(GarminDataProvider):
    async def login(
        self,
        email: str,
        password: str,
        prompt_mfa: Callable[[], str] | None = None,
    ) -> dict:
        def _login() -> Garmin:
            client = Garmin(email, password)
            try:
                client.login(prompt_mfa=prompt_mfa)
            except Exception as exc:
                if prompt_mfa is None and self._is_mfa_error(exc):
                    raise MFARequiredError(str(exc)) from exc
                raise
            return client

        client = await asyncio.to_thread(_login)
        return self.extract_tokens(client)

    def _is_mfa_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(marker in msg for marker in MFA_MARKERS)

    async def login_with_tokens(self, tokens: dict) -> Garmin:
        def _restore() -> Garmin:
            client = Garmin()
            if hasattr(client, "set_tokens"):
                client.set_tokens(tokens)
            elif hasattr(client, "garth") and client.garth:
                client.garth.loads(tokens)
            else:
                raise ValueError("Cannot restore Garmin session from tokens")
            return client

        return await asyncio.to_thread(_restore)

    async def get_activities(self, client: Garmin, start: int = 0, limit: int = 20) -> list[dict]:
        return await asyncio.to_thread(client.get_activities, start, limit)

    async def get_daily_stats(self, client: Garmin, target_date: date) -> dict:
        date_str = target_date.isoformat()
        stats = await asyncio.to_thread(client.get_stats, date_str)
        return stats or {}

    async def get_sleep_data(self, client: Garmin, target_date: date) -> dict:
        date_str = target_date.isoformat()
        try:
            return await asyncio.to_thread(client.get_sleep_data, date_str) or {}
        except Exception as exc:
            logger.warning("Failed to get sleep data for %s: %s", date_str, exc)
            return {}

    async def get_training_status(self, client: Garmin) -> dict:
        try:
            return await asyncio.to_thread(client.get_training_status) or {}
        except Exception as exc:
            logger.warning("Failed to get training status: %s", exc)
            return {}

    async def get_hrv_data(self, client: Garmin, target_date: date) -> dict:
        date_str = target_date.isoformat()
        try:
            return await asyncio.to_thread(client.get_hrv_data, date_str) or {}
        except Exception as exc:
            logger.warning("Failed to get HRV data for %s: %s", date_str, exc)
            return {}

    def extract_tokens(self, client: Garmin) -> dict:
        if hasattr(client, "get_tokens"):
            return client.get_tokens()
        if hasattr(client, "garth") and client.garth:
            return client.garth.dumps()
        raise ValueError("Unable to extract Garmin tokens from client")
