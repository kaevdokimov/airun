import contextvars
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def get_request_id() -> str | None:
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Expose the request ID to formatters without changing individual log calls."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
