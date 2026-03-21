from http import HTTPStatus
from typing import Any


class DomainError(Exception):
    status_code: int = 400
    error_code: str = "DOMAIN_ERROR"
    default_detail: str = "Domain operation failed"

    def __init__(
        self,
        detail: str | None = None,
        *,
        details: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        self.detail = detail or self.default_detail
        self.details = details
        self.error_code = error_code or self.error_code
        super().__init__(self.detail)


class BadRequestError(DomainError):
    status_code = 400
    error_code = "BAD_REQUEST"
    default_detail = "Bad request"


class UnauthorizedError(DomainError):
    status_code = 401
    error_code = "UNAUTHORIZED"
    default_detail = "Unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    error_code = "FORBIDDEN"
    default_detail = "Forbidden"


class NotFoundError(DomainError):
    status_code = 404
    error_code = "NOT_FOUND"
    default_detail = "Not found"


class ConflictError(DomainError):
    status_code = 409
    error_code = "CONFLICT"
    default_detail = "Conflict"


class UnprocessableEntityError(DomainError):
    status_code = 422
    error_code = "UNPROCESSABLE_ENTITY"
    default_detail = "Unprocessable entity"


class PayloadTooLargeError(DomainError):
    status_code = 413
    error_code = "PAYLOAD_TOO_LARGE"
    default_detail = "Payload too large"


def status_title(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"
