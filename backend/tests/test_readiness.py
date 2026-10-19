from starlette.testclient import TestClient

DRIVER_ERROR = 'asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "airun"'
REDIS_ERROR = "redis.exceptions.ConnectionError: Error 111 connecting to redis:6379. Connection refused."


async def _ok() -> None:
    return None


def _route_paths(routes) -> list[str]:
    paths: list[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.append(path)
        original = getattr(route, "original_router", None)
        if original is not None:
            paths.extend(_route_paths(original.routes))
        nested = getattr(route, "routes", None)
        if nested:
            paths.extend(_route_paths(nested))
    return paths


def test_health_and_ready_registered_once():
    from app.main import app

    paths = _route_paths(app.routes)
    assert paths.count("/health") == 1
    assert paths.count("/ready") == 1


def test_ready_hides_database_driver_error(client: TestClient, monkeypatch):
    async def fail_database() -> None:
        raise RuntimeError(DRIVER_ERROR)

    monkeypatch.setattr("app.main.check_database", fail_database)
    monkeypatch.setattr("app.main.check_redis", _ok)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "redis": "ok",
    }
    assert "password authentication" not in response.text
    assert "asyncpg" not in response.text


def test_ready_hides_redis_error(client: TestClient, monkeypatch):
    async def fail_redis() -> None:
        raise ConnectionError(REDIS_ERROR)

    monkeypatch.setattr("app.main.check_database", _ok)
    monkeypatch.setattr("app.main.check_redis", fail_redis)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ok",
        "redis": "unavailable",
    }
    assert "Connection refused" not in response.text
    assert "6379" not in response.text


def test_ready_ok_when_database_and_redis_respond(client: TestClient, monkeypatch):
    monkeypatch.setattr("app.main.check_database", _ok)
    monkeypatch.setattr("app.main.check_redis", _ok)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok", "redis": "ok"}
