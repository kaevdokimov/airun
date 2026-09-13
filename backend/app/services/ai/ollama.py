from app.config import get_settings
from app.services.ai.openai_chat import OpenAIChatProvider


class OllamaProvider(OpenAIChatProvider):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            base_url=settings.ollama_base_url,
            api_key=None,
            model=settings.ollama_model,
            provider_name="ollama",
            timeout=180.0,
        )
