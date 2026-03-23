from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.errors import UnauthorizedError
from core.http.cookies import clear_auth_cookies
from service.auth import TokenService, get_token_service

router = APIRouter()
security = HTTPBearer(
    auto_error=False,
    description="Send refresh token as Bearer for non-browser clients",
)


@router.post(
    path="/logout",
    responses={401: {"description": "Not authorized"}},
)
async def logout(
    request: Request,
    response: Response,
    svc: Annotated[TokenService, Depends(get_token_service)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, str]:
    refresh_cookie = request.cookies.get("refresh_token")
    refresh_header = (
        creds.credentials if creds and creds.scheme.lower() == "bearer" else None
    )

    token = refresh_cookie or refresh_header
    if token is None:
        raise UnauthorizedError("Refresh token is not passed")

    payload = await svc.revoke(token)
    if payload is None:
        raise UnauthorizedError("Invalid refresh token")

    if refresh_cookie:
        clear_auth_cookies(response)

    return {"message": "Logged out successfully"}
