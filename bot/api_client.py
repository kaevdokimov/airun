import logging
import os
from datetime import date

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str | None = None, bot_secret: str | None = None):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.bot_secret = bot_secret or os.getenv("INTERNAL_BOT_SECRET", "")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    def _headers(self, telegram_id: int | None = None) -> dict[str, str]:
        headers = {"X-Internal-Bot-Secret": self.bot_secret}
        if telegram_id is not None:
            headers["X-Bot-Telegram-Id"] = str(telegram_id)
        return headers

    async def close(self):
        await self.client.aclose()

    async def upsert_user(self, telegram_id: int, timezone: str = "Europe/Moscow") -> dict:
        r = await self.client.post(
            "/api/v1/users/telegram",
            json={"telegram_id": telegram_id, "timezone": timezone},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def garmin_connect(self, telegram_id: int, email: str, password: str) -> dict:
        r = await self.client.post(
            "/api/v1/garmin/connect",
            params={"telegram_id": telegram_id},
            json={"telegram_id": telegram_id, "email": email, "password": password},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def garmin_mfa(self, telegram_id: int, mfa_code: str) -> dict:
        r = await self.client.post(
            "/api/v1/garmin/mfa",
            params={"telegram_id": telegram_id},
            json={"telegram_id": telegram_id, "mfa_code": mfa_code},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def garmin_disconnect(self, telegram_id: int) -> dict:
        r = await self.client.delete(
            "/api/v1/garmin/disconnect",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def garmin_status(self, telegram_id: int) -> dict:
        r = await self.client.get(
            "/api/v1/garmin/status",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def list_goals(self, telegram_id: int) -> list:
        r = await self.client.get(
            "/api/v1/goals",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def create_goal(
        self,
        telegram_id: int,
        distance: str,
        race_date: date,
        target_time_seconds: int | None = None,
    ) -> dict:
        r = await self.client.post(
            "/api/v1/goals",
            params={"telegram_id": telegram_id},
            json={
                "distance": distance,
                "race_date": race_date.isoformat(),
                "target_time_seconds": target_time_seconds,
            },
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def delete_goal(self, telegram_id: int, goal_id: str) -> dict:
        r = await self.client.delete(
            f"/api/v1/goals/{goal_id}",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def stats_today(self, telegram_id: int) -> dict | None:
        r = await self.client.get(
            "/api/v1/stats/today",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def stats_week(self, telegram_id: int) -> dict:
        r = await self.client.get(
            "/api/v1/stats/week",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def latest_recommendation(self, telegram_id: int) -> dict | None:
        r = await self.client.get(
            "/api/v1/recommendations/latest",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def generate_recommendation(self, telegram_id: int, force: bool = False) -> dict:
        r = await self.client.post(
            "/api/v1/recommendations/generate",
            params={"telegram_id": telegram_id, "force": force},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()

    async def trigger_sync(self, telegram_id: int) -> dict:
        r = await self.client.post(
            "/api/v1/sync/trigger",
            params={"telegram_id": telegram_id},
            headers=self._headers(telegram_id),
        )
        r.raise_for_status()
        return r.json()
