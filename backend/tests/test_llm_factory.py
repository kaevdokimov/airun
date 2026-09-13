import pytest

from app.config import Settings
from app.services.ai.factory import get_available_providers, get_llm_provider
from app.services.ai.fallback import FallbackLLMProvider
from app.services.ai.groq_provider import GroqProvider
from app.services.ai.openrouter import OpenRouterProvider


@pytest.fixture
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_auto_selects_groq(clear_settings_cache, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_key")
    provider = get_llm_provider()
    assert isinstance(provider, FallbackLLMProvider)


def test_auto_single_provider(clear_settings_cache, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, GroqProvider)


def test_explicit_openrouter(clear_settings_cache, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    provider = get_llm_provider()
    assert isinstance(provider, OpenRouterProvider)


def test_no_providers_raises(clear_settings_cache, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    with pytest.raises(RuntimeError, match="No LLM provider"):
        get_llm_provider()


def test_available_providers_order(clear_settings_cache, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    settings = Settings()
    assert get_available_providers(settings) == ["groq", "openrouter", "ollama"]
