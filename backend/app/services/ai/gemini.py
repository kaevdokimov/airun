import logging

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas import RecommendationContent
from app.services.ai.base import LLMProvider
from app.services.ai.common import COACH_SYSTEM_INSTRUCTION, generate_recommendation_with_json_retry

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        return await generate_recommendation_with_json_retry(prompt, self._request_text)

    async def _request_text(self, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=COACH_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        return response.text or ""
