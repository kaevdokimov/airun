import logging

from starlette.testclient import TestClient

from app.api.middleware import RequestIdFormatter, request_id_var


def test_request_id_is_returned_and_available_to_logging(client: TestClient):
    response = client.get("/health", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"

    token = request_id_var.set("request-123")
    try:
        formatter = RequestIdFormatter(
            "%(levelname)s [request_id=%(request_id)s] %(message)s"
        )
        record = logging.makeLogRecord({"msg": "test", "levelno": logging.INFO, "levelname": "INFO"})
        assert "request_id=request-123" in formatter.format(record)
    finally:
        request_id_var.reset(token)


def test_request_id_formatter_defaults_when_context_empty():
    formatter = RequestIdFormatter("%(message)s [request_id=%(request_id)s]")
    record = logging.makeLogRecord({"msg": "outside-request", "levelno": logging.INFO})
    assert formatter.format(record) == "outside-request [request_id=-]"
