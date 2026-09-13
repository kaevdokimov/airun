from abc import ABC, abstractmethod

from app.schemas import RecommendationContent


class LLMProvider(ABC):
    @abstractmethod
    async def generate_recommendation(self, prompt: str) -> RecommendationContent:
        pass
