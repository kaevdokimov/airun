from groq import AsyncGroq

from app.config import get_settings
from app.schemas import RecommendationContent
from app.services.ai.base import LLMProvider
from app.services.ai.common import COACH_SYSTEM_INSTRUCTION, parse_recommendation_response


class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        return parse_recommendation_response(text)
