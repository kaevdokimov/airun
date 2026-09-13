import logging

from app.schemas import RecommendationContent
from app.services.ai.base import LLMProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider(LLMProvider):
    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackLLMProvider requires at least one provider")
        self.providers = providers

    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        errors: list[str] = []
        for provider in self.providers:
            name = provider.__class__.__name__
            try:
                return await provider.generate_recommendation(prompt)
            except Exception as exc:
                logger.warning("LLM provider %s failed: %s", name, exc)
                errors.append(f"{name}: {exc}")
        raise RuntimeError("All LLM providers failed: " + "; ".join(errors))
