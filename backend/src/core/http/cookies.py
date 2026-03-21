from typing import Any

from fastapi import Response

from core.config import Settings

settings = Settings()  # pyright: ignore[reportCallIssue]


def _base_cookie_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": settings.COOKIE_PATH,
    }
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    return kwargs


def set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    base_kwargs = _base_cookie_kwargs()
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.REFRESH_TTL,
        httponly=True,
        **base_kwargs,
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        max_age=settings.REFRESH_TTL,
        httponly=False,
        **base_kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    base_kwargs = _base_cookie_kwargs()
    response.delete_cookie(
        "refresh_token",
        httponly=True,
        **base_kwargs,
    )
    response.delete_cookie(
        "csrf_token",
        httponly=False,
        **base_kwargs,
    )
