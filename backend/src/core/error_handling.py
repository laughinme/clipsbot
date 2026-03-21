import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import Settings
from core.errors import DomainError, status_title


logger = logging.getLogger(__name__)


def _problem_response(
    *,
    request: Request,
    status_code: int,
    detail: str,
    error_code: str,
    details: Any | None = None,
    title: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title or status_title(status_code),
        "status": status_code,
        "detail": detail,
        "error_code": error_code,
        "instance": str(request.url.path),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    request_id = getattr(request.state, "request_id", None)
    if request_id:
        body["request_id"] = request_id

    if details is not None:
        body["details"] = details

    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _problem_response(
            request=request,
            status_code=exc.status_code,
            detail=exc.detail,
            error_code=exc.error_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _problem_response(
            request=request,
            status_code=422,
            detail="Request validation failed",
            error_code="REQUEST_VALIDATION_ERROR",
            details=exc.errors(),
        )

    async def _http_error_handler(
        request: Request,
        exc: HTTPException | StarletteHTTPException,
    ) -> JSONResponse:
        details: Any | None = None
        detail_text: str

        if isinstance(exc.detail, str):
            detail_text = exc.detail
        elif isinstance(exc.detail, dict):
            detail_text = str(exc.detail.get("detail") or "HTTP error")
            details = exc.detail
        elif isinstance(exc.detail, list):
            detail_text = "HTTP error"
            details = exc.detail
        else:
            detail_text = "HTTP error"

        return _problem_response(
            request=request,
            status_code=exc.status_code,
            detail=detail_text,
            error_code="HTTP_ERROR",
            details=details,
        )

    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled exception path=%s method=%s request_id=%s",
            request.url.path,
            request.method,
            request_id,
        )

        detail = "Internal server error"
        if settings.DEBUG:
            detail = f"{exc.__class__.__name__}: {exc}"

        return _problem_response(
            request=request,
            status_code=500,
            detail=detail,
            error_code="INTERNAL_SERVER_ERROR",
        )
