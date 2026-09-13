import json

# Bump when SYSTEM_PROMPT or context shape changes so cached LLM answers invalidate.
PROMPT_VERSION = "1"

SYSTEM_PROMPT = """Проанализируй данные тренировок и цели бегуна. Составь персональные рекомендации.

Верни JSON:
{
  "summary": "Краткий статус (2-3 предложения)",
  "today_recommendation": "Что делать сегодня",
  "week_plan": ["Пн: ...", "Вт: ...", "Ср: ...", "Чт: ...", "Пт: ...", "Сб: ...", "Вс: ..."],
  "warnings": ["предупреждения если есть"],
  "progress_to_goal": "оценка готовности к цели в процентах или словами"
}
"""


def build_recommendation_prompt(context: dict) -> str:
    return f"""{SYSTEM_PROMPT}

Данные бегуна:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""
