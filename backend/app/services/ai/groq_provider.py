from groq import AsyncGroq

from app.config import get_settings
from app.schemas import RecommendationContent
from app.services.ai.base import LLMProvider
from app.services.ai.common import COACH_SYSTEM_INSTRUCTION, generate_recommendation_with_json_retry


class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        return await generate_recommendation_with_json_retry(prompt, self._request_text)

    async def _request_text(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
