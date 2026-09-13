import logging

import httpx

from app.schemas import RecommendationContent
from app.services.ai.base import LLMProvider
from app.services.ai.common import COACH_SYSTEM_INSTRUCTION, parse_recommendation_response

logger = logging.getLogger(__name__)


class OpenAIChatProvider(LLMProvider):
    """OpenAI-compatible chat API (Groq, OpenRouter, Ollama, etc.)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
        provider_name: str = "openai-chat",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.extra_headers = extra_headers or {}
        self.provider_name = provider_name
        self.timeout = timeout

    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": COACH_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"] or ""
        return parse_recommendation_response(text)
