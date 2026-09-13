"""Shared helpers for API tests."""

BOT_SECRET = "test-bot-secret-32-characters-min!"
TELEGRAM_ID = 12345


def bot_headers(telegram_id: int = TELEGRAM_ID) -> dict[str, str]:
    return {
        "X-Internal-Bot-Secret": BOT_SECRET,
        "X-Bot-Telegram-Id": str(telegram_id),
    }
