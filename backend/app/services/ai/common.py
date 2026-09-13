import json
import logging
import re
from collections.abc import Awaitable, Callable

from app.schemas import RecommendationContent

logger = logging.getLogger(__name__)

COACH_SYSTEM_INSTRUCTION = """Ты — опытный беговой тренер. Даёшь персональные рекомендации на основе данных Garmin.
Правила:
- Учитывай дату забега и обратный отсчёт
- Если указано целевое время — оценивай текущий темп vs целевой
- Не давай медицинских советов, только тренировочные
- Отвечай на русском языке
- Ответ строго в JSON формате:
{"summary":"","today_recommendation":"","week_plan":[],"warnings":[],"progress_to_goal":""}"""


JSON_REPAIR_PROMPT = """Предыдущий ответ был невалидным JSON.
Верни только один валидный JSON-объект без markdown и пояснений строго по схеме:
{{"summary":"","today_recommendation":"","week_plan":[],"warnings":[],"progress_to_goal":""}}

Исходный запрос:
{prompt}

Невалидный ответ:
{bad_response}"""


def _parse_recommendation_response_strict(text: str) -> RecommendationContent:
    try:
        data = json.loads(text)
        return RecommendationContent.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group())
        return RecommendationContent.model_validate(data)


def parse_recommendation_response(text: str) -> RecommendationContent:
    try:
        return _parse_recommendation_response_strict(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM response, using raw text")
        return RecommendationContent(
            summary=text[:500],
            today_recommendation="См. полный текст рекомендации выше.",
        )


async def generate_recommendation_with_json_retry(
    prompt: str,
    request_text: Callable[[str], Awaitable[str]],
    *,
    max_attempts: int = 3,
) -> RecommendationContent:
    current_prompt = prompt
    last_text = ""
    for attempt in range(max_attempts):
        last_text = await request_text(current_prompt)
        try:
            return _parse_recommendation_response_strict(last_text)
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == max_attempts - 1:
                logger.warning("Failed to parse LLM response after %s attempts: %s", max_attempts, exc)
                break
            current_prompt = JSON_REPAIR_PROMPT.format(prompt=prompt, bad_response=last_text[:4000])

    return RecommendationContent(
        summary=last_text[:500],
        today_recommendation="См. полный текст рекомендации выше.",
    )
