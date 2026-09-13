import logging

from starlette.testclient import TestClient

from app.api.middleware import RequestIdFilter, request_id_var


def test_request_id_is_returned_and_available_to_logging(client: TestClient):
    response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"

    token = request_id_var.set("request-123")
    try:
        record = logging.makeLogRecord({"msg": "test"})
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "request-123"
    finally:
        request_id_var.reset(token)
