from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Callable


class GarminDataProvider(ABC):
    @abstractmethod
    async def login(
        self,
        email: str,
        password: str,
        prompt_mfa: Callable[[], str] | None = None,
    ) -> dict:
        """Authenticate and return token dict."""

    @abstractmethod
    async def login_with_tokens(self, tokens: dict) -> Any:
        """Restore session from saved tokens."""

    @abstractmethod
    async def get_activities(self, client: Any, start: int = 0, limit: int = 20) -> list[dict]:
        pass

    @abstractmethod
    async def get_daily_stats(self, client: Any, target_date: date) -> dict:
        pass

    @abstractmethod
    async def get_sleep_data(self, client: Any, target_date: date) -> dict:
        pass

    @abstractmethod
    async def get_training_status(self, client: Any) -> dict:
        pass

    @abstractmethod
    async def get_hrv_data(self, client: Any, target_date: date) -> dict:
        pass

    @abstractmethod
    def extract_tokens(self, client: Any) -> dict:
        pass
