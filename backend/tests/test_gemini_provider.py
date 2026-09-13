from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai.gemini import GeminiProvider


@pytest.mark.asyncio
async def test_gemini_provider_uses_async_client():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-test"
    provider.client = MagicMock()
    provider.client.aio.models.generate_content = AsyncMock(
        return_value=SimpleNamespace(text="response text")
    )

    result = await provider._request_text("prompt")

    assert result == "response text"
    provider.client.aio.models.generate_content.assert_awaited_once()
