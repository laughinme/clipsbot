from typing import Annotated

from fastapi import APIRouter, Depends, Response

from core.http.cookies import set_auth_cookies
from core.rate_limit import AUTH_LIMITER_STATE_KEY, build_rate_dependency
from domain.auth import TelegramAuthRequest, TokenPair
from service.auth import TelegramAuthService, get_telegram_auth_service

router = APIRouter()
auth_rate_limit = build_rate_dependency(AUTH_LIMITER_STATE_KEY)


@router.post(
    path="/telegram",
    response_model=TokenPair,
    summary="Authenticate Telegram Mini App user",
    dependencies=[Depends(auth_rate_limit)],
)
async def telegram_auth(
    response: Response,
    payload: TelegramAuthRequest,
    svc: Annotated[TelegramAuthService, Depends(get_telegram_auth_service)],
) -> TokenPair:
    access, refresh, csrf, _ = await svc.authenticate(payload.init_data)
    set_auth_cookies(response, refresh, csrf)
    return TokenPair(access_token=access, refresh_token=None)
