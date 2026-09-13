from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware

from api_client import APIClient


class APIClientMiddleware(BaseMiddleware):
    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        data["api"] = self.api_client
        return await handler(event, data)
