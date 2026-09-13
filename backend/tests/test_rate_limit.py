from app.limiter import limiter


def test_health_rate_limit_returns_429(client):
    limiter._storage.reset()

    statuses = [client.get("/health").status_code for _ in range(70)]
    assert 200 in statuses
    assert 429 in statuses
    first_limited = statuses.index(429)
    assert first_limited == 60
    assert all(code == 429 for code in statuses[first_limited:])


def test_telegram_web_auth_rate_limit_returns_429(client, monkeypatch):
    limiter._storage.reset()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    from app.config import get_settings

    get_settings.cache_clear()

    payload = {
        "id": 1,
        "first_name": "Test",
        "auth_date": 1_700_000_000,
        "hash": "invalid",
    }
    for _ in range(10):
        response = client.post("/api/v1/auth/telegram-web", json=payload)
        assert response.status_code != 429

    limited = client.post("/api/v1/auth/telegram-web", json=payload)
    assert limited.status_code == 429
