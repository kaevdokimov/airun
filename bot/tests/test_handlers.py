import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import (
    format_duration,
    format_recommendation,
    garmin_mfa,
    garmin_password,
    goal_delete,
    goal_race_date,
    recommendations,
    stats,
    sync,
)


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


def _message(text: str = "") -> MagicMock:
    message = MagicMock()
    message.from_user.id = 12345
    message.text = text
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    return message


def _state(data: dict | None = None) -> AsyncMock:
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.clear = AsyncMock()
    return state


def _answers(message: MagicMock) -> list[str]:
    return [call.args[0] for call in message.answer.await_args_list]


@pytest.mark.asyncio
async def test_garmin_password_hides_exception(caplog):
    password = "secret-garmin-password"
    message = _message(password)
    state = _state({"email": "runner@example.com"})
    api = AsyncMock()
    api.garmin_connect = AsyncMock(side_effect=RuntimeError(f"auth failed for {password}"))

    with caplog.at_level(logging.ERROR):
        await garmin_password(message, state, api)

    texts = " ".join(_answers(message))
    assert "Не удалось подключить Garmin" in texts
    assert password not in texts
    assert password not in caplog.text
    assert "RuntimeError" in caplog.text
    state.clear.assert_awaited()


@pytest.mark.asyncio
async def test_garmin_mfa_hides_exception(caplog):
    code = "482913"
    message = _message(code)
    state = _state()
    api = AsyncMock()
    api.garmin_mfa = AsyncMock(side_effect=RuntimeError(f"mfa {code} rejected"))

    with caplog.at_level(logging.ERROR):
        await garmin_mfa(message, state, api)

    texts = " ".join(_answers(message))
    assert "Не удалось подтвердить код MFA" in texts
    assert code not in texts
    assert code not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_goal_race_date_api_error_keeps_state(caplog):
    message = _message("01.06.2027")
    state = _state({"distance": "5k", "target_time_seconds": None})
    api = AsyncMock()
    api.create_goal = AsyncMock(side_effect=RuntimeError("sqlite constraint telegram token"))

    with caplog.at_level(logging.ERROR):
        await goal_race_date(message, state, api)

    assert "Не удалось создать цель" in _answers(message)[-1]
    assert "sqlite" not in _answers(message)[-1]
    assert "token" not in caplog.text
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_goal_delete_api_error():
    callback = MagicMock()
    callback.data = "goal_del:goal-1"
    callback.from_user.id = 12345
    callback.answer = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    api = AsyncMock()
    api.delete_goal = AsyncMock(side_effect=RuntimeError("internal goal id leak"))

    await goal_delete(callback, api)

    text = callback.message.answer.await_args.args[0]
    assert text == "Не удалось удалить цель."
    assert "leak" not in text
    callback.answer.assert_awaited()
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_stats_api_error():
    message = _message()
    api = AsyncMock()
    api.stats_today = AsyncMock(side_effect=RuntimeError("db password in driver message"))

    await stats(message, api)

    assert _answers(message) == ["Не удалось загрузить статистику."]


@pytest.mark.asyncio
async def test_recommendations_api_error():
    message = _message()
    api = AsyncMock()
    api.latest_recommendation = AsyncMock(side_effect=RuntimeError("llm key sk-secret"))

    await recommendations(message, api)

    assert _answers(message) == ["Не удалось загрузить рекомендации."]
    assert "sk-secret" not in _answers(message)[0]


@pytest.mark.asyncio
async def test_sync_handler_exception_is_generic(caplog):
    message = _message()
    api = AsyncMock()
    api.trigger_sync = AsyncMock(side_effect=RuntimeError("token garmin-oauth-secret"))

    with caplog.at_level(logging.ERROR):
        await sync(message, api)

    assert _answers(message)[-1] == "Не удалось синхронизировать данные Garmin."
    assert "garmin-oauth-secret" not in caplog.text
    assert "RuntimeError" in caplog.text
