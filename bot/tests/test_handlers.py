from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import format_duration, format_recommendation, sync


def test_format_duration_none():
    assert format_duration(None) == "—"


def test_format_duration_minutes():
    assert format_duration(125) == "2:05"


def test_format_duration_hours():
    assert format_duration(3661) == "1:01:01"


def test_format_recommendation_parsed():
    text = format_recommendation(
        {
            "parsed": {
                "summary": "Хорошая форма",
                "today_recommendation": "Легкий бег 5 км",
                "week_plan": ["Пн: отдых", "Вт: 8 км"],
                "warnings": ["Недосып"],
                "progress_to_goal": "70%",
            }
        }
    )
    assert "Хорошая форма" in text
    assert "Легкий бег 5 км" in text
    assert "70%" in text
    assert "Пн: отдых" in text
    assert "Недосып" in text


def test_format_recommendation_fallback_content():
    assert format_recommendation({"content": "сырой текст"}) == "сырой текст"


@pytest.mark.asyncio
async def test_sync_handler_success_message():
    message = MagicMock()
    message.from_user.id = 12345
    message.answer = AsyncMock()

    api = AsyncMock()
    api.trigger_sync = AsyncMock(
        return_value={
            "success": True,
            "message": "Синхронизация завершена",
            "activities_synced": 2,
            "summaries_synced": 3,
        }
    )

    await sync(message, api)

    assert message.answer.await_count == 2
    final_text = message.answer.await_args_list[1].args[0]
    assert "Синхронизация завершена" in final_text
    assert "Активностей: 2" in final_text
    assert "сводок: 3" in final_text


@pytest.mark.asyncio
async def test_sync_handler_error_message():
    message = MagicMock()
    message.from_user.id = 12345
    message.answer = AsyncMock()

    api = AsyncMock()
    api.trigger_sync = AsyncMock(
        return_value={"success": False, "message": "Garmin не подключен"}
    )

    await sync(message, api)

    final_text = message.answer.await_args_list[1].args[0]
    assert "Garmin не подключен" in final_text
