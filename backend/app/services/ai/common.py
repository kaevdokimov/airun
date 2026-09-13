import json
import logging
import re

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


def parse_recommendation_response(text: str) -> RecommendationContent:
    try:
        data = json.loads(text)
        return RecommendationContent.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return RecommendationContent.model_validate(data)
        logger.warning("Failed to parse LLM response, using raw text")
        return RecommendationContent(
            summary=text[:500],
            today_recommendation="См. полный текст рекомендации выше.",
        )
