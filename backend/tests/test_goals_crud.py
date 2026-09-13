from datetime import date, timedelta

from starlette.testclient import TestClient

TELEGRAM_ID = 12345


def bot_headers(telegram_id: int = TELEGRAM_ID) -> dict[str, str]:
    return {
        "X-Internal-Bot-Secret": "test-bot-secret-32-characters-min!",
        "X-Bot-Telegram-Id": str(telegram_id),
    }


def future_race_date(days: int = 30) -> date:
    return date.today() + timedelta(days=days)


def _upsert_user(client: TestClient, telegram_id: int = TELEGRAM_ID) -> None:
    response = client.post(
        "/api/v1/users/telegram",
        json={"telegram_id": telegram_id, "timezone": "Europe/Moscow"},
        headers=bot_headers(telegram_id),
    )
    assert response.status_code == 200
    assert response.json()["telegram_id"] == telegram_id


def test_goal_crud_flow(client: TestClient):
    _upsert_user(client)
    race_date = future_race_date(45).isoformat()

    create = client.post(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
        json={"distance": "10k", "target_time_seconds": 3000, "race_date": race_date},
    )
    assert create.status_code == 200
    goal = create.json()
    assert goal["distance"] == "10k"
    assert goal["target_time_seconds"] == 3000
    assert goal["status"] == "active"
    goal_id = goal["id"]

    listed = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == goal_id

    updated = client.patch(
        f"/api/v1/goals/{goal_id}",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
        json={"target_time_seconds": 2800, "status": "completed"},
    )
    assert updated.status_code == 200
    assert updated.json()["target_time_seconds"] == 2800
    assert updated.json()["status"] == "completed"

    deleted = client.delete(
        f"/api/v1/goals/{goal_id}",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    after = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
    )
    assert after.status_code == 200
    assert after.json() == []


def test_create_goal_rejects_past_race_date(client: TestClient):
    _upsert_user(client)
    past = (date.today() - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
        json={"distance": "5k", "race_date": past},
    )
    assert response.status_code == 400
    assert "будущем" in response.json()["detail"]


def test_update_missing_goal_returns_404(client: TestClient):
    _upsert_user(client)
    response = client.patch(
        "/api/v1/goals/00000000-0000-0000-0000-000000000001",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
        json={"status": "cancelled"},
    )
    assert response.status_code == 404


def test_goals_require_existing_user(client: TestClient):
    response = client.get(
        "/api/v1/goals",
        params={"telegram_id": TELEGRAM_ID},
        headers=bot_headers(),
    )
    assert response.status_code == 404
