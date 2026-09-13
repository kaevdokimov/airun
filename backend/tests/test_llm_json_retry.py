from unittest.mock import AsyncMock

import pytest

from app.services.ai.common import JSON_REPAIR_PROMPT, generate_recommendation_with_json_retry


@pytest.mark.asyncio
async def test_json_retry_repairs_invalid_response_on_second_attempt():
    request_text = AsyncMock(
        side_effect=[
            "not valid json",
            '{"summary":"Готово","today_recommendation":"Отдых","week_plan":[],"warnings":[],"progress_to_goal":"ok"}',
        ]
    )

    result = await generate_recommendation_with_json_retry("initial prompt", request_text)

    assert result.summary == "Готово"
    assert request_text.await_count == 2
    repair_prompt = request_text.await_args_list[1].args[0]
    assert repair_prompt == JSON_REPAIR_PROMPT.format(
        prompt="initial prompt",
        bad_response="not valid json",
    )
    assert '"summary"' in repair_prompt


@pytest.mark.asyncio
async def test_json_retry_returns_soft_fallback_after_all_attempts_fail():
    request_text = AsyncMock(side_effect=["broken one", "broken two", "broken three"])

    result = await generate_recommendation_with_json_retry("initial prompt", request_text)

    assert request_text.await_count == 3
    assert result.summary == "broken three"
    assert result.today_recommendation == "См. полный текст рекомендации выше."
