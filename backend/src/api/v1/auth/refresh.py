from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.errors import ForbiddenError, UnauthorizedError
from core.rate_limit import REFRESH_LIMITER_STATE_KEY, build_rate_dependency
from service.auth import TokenService, get_token_service
from domain.auth import TokenPair
from core.http.cookies import clear_auth_cookies, set_auth_cookies
from core.security import extract_jti

router = APIRouter()
security = HTTPBearer(
    auto_error=False, 
    description='Send refresh token as Bearer for non browser clients'
)
refresh_rate_limit = build_rate_dependency(
    REFRESH_LIMITER_STATE_KEY,
    identifier=extract_jti,
)


@router.post(
    path='/refresh',
    response_model=TokenPair,
    summary='Rotate tokens',
    dependencies=[Depends(refresh_rate_limit)],
)
async def refresh_tokens(
    request: Request,
    response: Response,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    svc: Annotated[TokenService, Depends(get_token_service)],
    x_csrf: str | None = Header(
        default=None, alias="X-CSRF-Token", 
        description='Must only be passed for requests from browsers'
    ),
) -> TokenPair:
    cookie_refresh = request.cookies.get("refresh_token")
    
    if cookie_refresh:
        if not x_csrf:
            raise ForbiddenError("Missing CSRF token")
        
        result = await svc.refresh_tokens(cookie_refresh, x_csrf)
        if result is None:
            # token invalid or csrf mismatch
            clear_auth_cookies(response)
            raise UnauthorizedError("Invalid refresh token")
        
        new_access, new_refresh, new_csrf = result
        
        # set fresh cookies
        set_auth_cookies(response, new_refresh, new_csrf)

        # body: only short-lived access token
        return TokenPair(access_token=new_access, refresh_token=None)
        
    if not creds or creds.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing refresh token")
    
    result = await svc.refresh_tokens(creds.credentials)
    if result is None:
        raise UnauthorizedError("Invalid refresh token")

    new_access, new_refresh, _ = result
    return TokenPair(access_token=new_access, refresh_token=new_refresh)
