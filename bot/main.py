import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from pydantic_settings import BaseSettings, SettingsConfigDict

from api_client import APIClient
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    internal_bot_secret: str
    api_base_url: str = "http://localhost:8000"
    redis_url: str = "redis://localhost:6379/0"


async def notification_listener(bot: Bot, api: APIClient, redis_url: str):
    redis = aioredis.from_url(redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe("telegram_notifications")
    logger.info("Listening for telegram notifications")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            telegram_id = data["telegram_id"]
            event = data["event"]

            if event == "morning_digest":
                rec = await api.latest_recommendation(telegram_id)
                if rec:
                    from handlers import format_recommendation

                    await bot.send_message(
                        telegram_id,
                        f"🌅 *Утренние рекомендации*\n\n{format_recommendation(rec)}",
                        parse_mode="Markdown",
                    )
            elif event == "new_activity":
                await bot.send_message(telegram_id, "🏃 Новая пробежка синхронизирована! Проверьте рекомендации.")
            elif event.startswith("race_reminder_"):
                days = event.split("_")[-1]
                await bot.send_message(
                    telegram_id,
                    f"🏁 До вашего забега осталось *{days}* {'день' if days == '1' else 'дня' if days == '3' else 'дней'}!",
                    parse_mode="Markdown",
                )
        except Exception as exc:
            logger.error("Notification error: %s", exc)


async def main():
    settings = BotSettings()
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    api = APIClient(settings.api_base_url, settings.internal_bot_secret)

    from aiogram import BaseMiddleware
    from typing import Any, Awaitable, Callable

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

    dp.message.middleware(APIClientMiddleware(api))
    dp.callback_query.middleware(APIClientMiddleware(api))
    dp.include_router(router)

    listener_task = asyncio.create_task(
        notification_listener(bot, api, settings.redis_url)
    )

    try:
        await dp.start_polling(bot)
    finally:
        listener_task.cancel()
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
