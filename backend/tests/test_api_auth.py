import pytest
from cryptography.fernet import Fernet
from starlette.testclient import TestClient

BOT_SECRET = "test-bot-secret-32-characters-min!"
JWT_SECRET = "test-jwt-secret-32-characters-min!!"
TELEGRAM_ID = 12345


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("INTERNAL_BOT_SECRET", BOT_SECRET)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()
    from app.services import security as security_mod

    security_mod._encryption = None


@pytest.fixture
def client(auth_env):
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def bot_headers(telegram_id: int = TELEGRAM_ID) -> dict[str, str]:
    return {
        "X-Internal-Bot-Secret": BOT_SECRET,
        "X-Bot-Telegram-Id": str(telegram_id),
    }


def test_goals_requires_auth(client: TestClient):
    response = client.get("/api/v1/goals", params={"telegram_id": TELEGRAM_ID})
    assert response.status_code == 401


def test_goals_rejects_wrong_bot_secret(client: TestClient):
    response = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers={"X-Internal-Bot-Secret": "wrong", "X-Bot-Telegram-Id": str(TELEGRAM_ID)},
    )
    assert response.status_code == 401


def test_goals_rejects_mismatched_bot_telegram_id(client: TestClient):
    response = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(telegram_id=99999),
    )
    assert response.status_code == 403


def test_goals_rejects_invalid_bot_telegram_id_header(client: TestClient):
    response = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers={"X-Internal-Bot-Secret": BOT_SECRET, "X-Bot-Telegram-Id": "not-a-number"},
    )
    assert response.status_code == 400


def test_upsert_rejects_mismatched_bot_telegram_id(client: TestClient):
    response = client.post(
        "/api/v1/users/telegram",
        json={"telegram_id": TELEGRAM_ID, "timezone": "Europe/Moscow"},
        headers=bot_headers(telegram_id=99999),
    )
    assert response.status_code == 403


def test_jwt_token_mismatch_returns_403(client: TestClient):
    from app.api.deps import create_access_token

    token = create_access_token(TELEGRAM_ID)
    response = client.get(
        "/api/v1/goals",
        params={"telegram_id": 99999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
