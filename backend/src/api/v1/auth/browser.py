from typing import Annotated

from fastapi import APIRouter, Depends, Response

from core.http.cookies import set_auth_cookies
from core.rate_limit import AUTH_LIMITER_STATE_KEY, build_rate_dependency
from domain.auth import (
    BrowserAuthCompleteRequest,
    BrowserAuthCompleteResponse,
    BrowserAuthStartResponse,
    BrowserAuthStatusResponse,
)
from service.auth import BrowserAuthService, get_browser_auth_service

router = APIRouter()
auth_rate_limit = build_rate_dependency(AUTH_LIMITER_STATE_KEY)


@router.post(
    path="/browser/start",
    response_model=BrowserAuthStartResponse,
    summary="Start browser login via Telegram bot",
    dependencies=[Depends(auth_rate_limit)],
)
async def start_browser_auth(
    svc: Annotated[BrowserAuthService, Depends(get_browser_auth_service)],
) -> BrowserAuthStartResponse:
    challenge = await svc.start()
    return BrowserAuthStartResponse.model_validate(svc.build_start_response_payload(challenge))


@router.get(
    path="/browser/status/{challenge_token}",
    response_model=BrowserAuthStatusResponse,
    summary="Check browser login challenge status",
)
async def get_browser_auth_status(
    challenge_token: str,
    svc: Annotated[BrowserAuthService, Depends(get_browser_auth_service)],
) -> BrowserAuthStatusResponse:
    challenge = await svc.get_status(challenge_token)
    return BrowserAuthStatusResponse.model_validate(svc.build_status_response_payload(challenge))


@router.post(
    path="/browser/complete",
    response_model=BrowserAuthCompleteResponse,
    summary="Complete browser login after Telegram confirmation",
    dependencies=[Depends(auth_rate_limit)],
)
async def complete_browser_auth(
    response: Response,
    payload: BrowserAuthCompleteRequest,
    svc: Annotated[BrowserAuthService, Depends(get_browser_auth_service)],
) -> BrowserAuthCompleteResponse:
    access, refresh, csrf = await svc.complete(payload.challenge_token)
    set_auth_cookies(response, refresh, csrf)
    return BrowserAuthCompleteResponse(access_token=access, refresh_token=None)
