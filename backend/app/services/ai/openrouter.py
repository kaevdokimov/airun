from app.config import get_settings
from app.services.ai.openai_chat import OpenAIChatProvider


class OpenRouterProvider(OpenAIChatProvider):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            extra_headers={
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": "AIRun",
            },
            provider_name="openrouter",
        )
