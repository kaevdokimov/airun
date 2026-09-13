import logging

from app.config import Settings, get_settings
from app.services.ai.base import LLMProvider
from app.services.ai.fallback import FallbackLLMProvider
from app.services.ai.gemini import GeminiProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.ollama import OllamaProvider
from app.services.ai.openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)

AUTO_PROVIDER_ORDER = ("groq", "openrouter", "ollama", "gemini")


def _provider_available(settings: Settings, name: str) -> bool:
    if name == "groq":
        return bool(settings.groq_api_key)
    if name == "openrouter":
        return bool(settings.openrouter_api_key)
    if name == "ollama":
        return settings.ollama_enabled
    if name == "gemini":
        return bool(settings.gemini_api_key)
    return False


def _build_provider(settings: Settings, name: str) -> LLMProvider | None:
    if not _provider_available(settings, name):
        return None
    if name == "groq":
        return GroqProvider()
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "ollama":
        return OllamaProvider()
    if name == "gemini":
        return GeminiProvider()
    return None


def get_available_providers(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    return [name for name in AUTO_PROVIDER_ORDER if _provider_available(settings, name)]


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "auto":
        providers = [
            provider
            for name in AUTO_PROVIDER_ORDER
            if (provider := _build_provider(settings, name)) is not None
        ]
        if not providers:
            raise RuntimeError(
                "No LLM provider configured. Set GROQ_API_KEY, OPENROUTER_API_KEY, "
                "enable OLLAMA_ENABLED=true, or GEMINI_API_KEY."
            )
        if len(providers) == 1:
            return providers[0]
        return FallbackLLMProvider(providers)

    provider = _build_provider(settings, provider_name)
    if provider is None:
        raise RuntimeError(
            f"LLM provider '{provider_name}' is not configured. "
            "Check API keys and LLM_PROVIDER in .env."
        )
    return provider


def log_llm_startup_status() -> None:
    settings = get_settings()
    available = get_available_providers(settings)
    if not available:
        logger.warning(
            "No LLM providers configured — AI recommendations will fail until "
            "GROQ_API_KEY, OPENROUTER_API_KEY, OLLAMA_ENABLED, or GEMINI_API_KEY is set"
        )
        return
    if settings.llm_provider.lower() == "auto":
        logger.info("LLM auto mode, available providers: %s", ", ".join(available))
    else:
        logger.info("LLM provider: %s", settings.llm_provider)
