from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.models import Recommendation, User

TELEGRAM_ID = 12345


def bot_headers(telegram_id: int = TELEGRAM_ID) -> dict[str, str]:
    return {
        "X-Internal-Bot-Secret": "test-bot-secret-32-characters-min!",
        "X-Bot-Telegram-Id": str(telegram_id),
    }


def _upsert_user(client: TestClient) -> str:
    response = client.post(
        "/api/v1/users/telegram",
        json={"telegram_id": TELEGRAM_ID, "timezone": "Europe/Moscow"},
        headers=bot_headers(),
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.mark.asyncio
async def test_latest_recommendation_returns_most_recent_record(client: TestClient, db_session):
    _upsert_user(client)
    user = (await db_session.execute(select(User).where(User.telegram_id == TELEGRAM_ID))).scalar_one()
    recommendation = Recommendation(
        user_id=user.id,
        content='{"summary":"Последняя","today_recommendation":"Бег","week_plan":[],"warnings":[],"progress_to_goal":"ok"}',
        context_snapshot={"goals": []},
    )
    db_session.add(recommendation)
    await db_session.commit()

    response = client.get(
        "/api/v1/recommendations/latest",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(recommendation.id)
    assert response.json()["parsed"]["summary"] == "Последняя"


def test_generate_recommendation_uses_service_and_returns_response(client: TestClient):
    _upsert_user(client)
    generated = Recommendation(
        id=uuid4(),
        user_id=uuid4(),
        content='{"summary":"Новая","today_recommendation":"Лёгкий бег","week_plan":[],"warnings":[],"progress_to_goal":"ok"}',
        context_snapshot={"goals": []},
        generated_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.api.v1.routes.recommendations.recommendation_service.generate",
        new=AsyncMock(return_value=generated),
    ) as generate:
        response = client.post(
            "/api/v1/recommendations/generate",
            params={"telegram_id": TELEGRAM_ID, "force": "true"},
            headers=bot_headers(),
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["recommendation"]["id"] == str(generated.id)
    generate.assert_awaited_once()
