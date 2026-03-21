import logging
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


def _resolve_request_id(headers: Headers) -> str:
    incoming = headers.get("X-Request-ID") or headers.get("X-Correlation-ID")
    if incoming:
        stripped = incoming.strip()
        if stripped:
            return stripped
    return uuid4().hex


class RequestTracingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _resolve_request_id(headers)

        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        method = scope.get("method", "")
        path = scope.get("path", "")
        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                duration_ms = (time.perf_counter() - started) * 1000
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
                method,
                path,
                status_code,
                duration_ms,
                request_id,
            )
