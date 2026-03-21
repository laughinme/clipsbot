from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Response, Header

from core.http.cookies import set_auth_cookies
from service.auth import CredentialsService, get_credentials_service
from domain.auth import UserRegister,  TokenPair

router = APIRouter()


@router.post(
    path='/register',
    response_model=TokenPair,
    status_code=201,
    responses={
        201: {
            'description': 'refresh_token field varies depending on the source of request. ' \
            'For web it is always null and being set as httponly cookie, ' \
            'however any other platform gets access and refresh tokens in response body. ' \
            'It is made to protect web from xss and csrf attacks'
        },
        409: {"description": "User with provided credentials already exists"}
    }
)
async def register_user(
    response: Response,
    payload: UserRegister,
    svc: Annotated[CredentialsService, Depends(get_credentials_service)],
    client: Literal['web', 'mobile'] = Header('web', alias='X-Client'),
) -> TokenPair:
    access, refresh, csrf = await svc.register(payload, client)
    
    if client == 'web':
        set_auth_cookies(response, refresh, csrf)
    
        return TokenPair(access_token=access, refresh_token=None)
    
    return TokenPair(access_token=access, refresh_token=refresh)
