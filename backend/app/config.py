from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://airun:airun@localhost:5432/airun"
    database_url_sync: str = "postgresql://airun:airun@localhost:5432/airun"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    internal_bot_secret: str = ""
    jwt_secret: str = ""

    gemini_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_app_url: str = "http://localhost:3000"
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"
    llm_provider: str = "auto"

    credentials_encryption_key: str = ""

    sync_interval_minutes: int = 15
    recommendation_cooldown_hours: int = 1
    # 0 disables. Effective TTL is max(this, cooldown_hours*3600 + 300) so repeated
    # generate after cooldown can reuse the LLM answer when context is unchanged.
    llm_cache_ttl_seconds: int = 3900

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
