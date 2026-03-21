from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Response, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.errors import UnauthorizedError
from core.http.cookies import clear_auth_cookies, set_auth_cookies
from service.auth import CredentialsService, get_credentials_service
from domain.auth import UserLogin, TokenPair

router = APIRouter()
security = HTTPBearer(
    auto_error=False, 
    description='Send refresh token as Bearer for non-browser clients'
)


@router.post(
    path="/login",
    response_model=TokenPair,
    summary="Authenticate user and issue tokens",
    responses={        
        200: {
            'description': 'refresh_token field varies depending on the source of request. ' \
            'For web it is always null and being set as httponly cookie, ' \
            'however any other platform gets access and refresh tokens in response body. ' \
            'It is made to protect web from xss and csrf attacks'
        },
        401: {"description": "Wrong credentials"}
    }
)
async def login_user(
    response: Response,
    payload: UserLogin,
    svc: Annotated[CredentialsService, Depends(get_credentials_service)],
    client: Literal['web', 'mobile'] = Header('web', alias='X-Client'),
) -> TokenPair:
    access, refresh, csrf = await svc.login(payload, client)
    
    if client == 'web':
        set_auth_cookies(response, refresh, csrf)
    
        return TokenPair(access_token=access, refresh_token=None)
    
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post(
    path="/logout",
    responses={401: {"description": "Not authorized"}}
)
async def logout(
    request: Request,
    response: Response,
    svc: Annotated[CredentialsService, Depends(get_credentials_service)],
    creds: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> dict:
    refresh_cookie = request.cookies.get("refresh_token")
    
    refresh_header = (
        creds.credentials if creds and creds.scheme.lower() == "bearer" else None
    )

    token = refresh_cookie or refresh_header
    if token is None:
        raise UnauthorizedError("Refresh token is not passed")
    
    await svc.logout(token)
    
    if refresh_cookie:
        clear_auth_cookies(response)
        
    return {'message': 'Logged out successfully'}
