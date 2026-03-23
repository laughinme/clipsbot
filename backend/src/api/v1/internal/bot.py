from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.security import require_internal_service
from domain.auth import BrowserAuthInternalConfirmRequest, BrowserAuthStatusResponse
from domain.clips import ClipSearchResponse
from domain.users import UploaderInviteConsumeRequest, UploaderInviteConsumeResponse
from service.auth import BrowserAuthService, get_browser_auth_service
from service.clips import ClipService, get_clip_service
from service.users import UploaderInviteService, get_uploader_invite_service

router = APIRouter(prefix="/bot", dependencies=[Depends(require_internal_service)])


@router.get(
    path="/clips/search",
    response_model=ClipSearchResponse,
    summary="Internal bot clip search",
)
async def bot_search_clips(
    svc: Annotated[ClipService, Depends(get_clip_service)],
    query: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    return await svc.search_for_bot(query=query, limit=limit)


@router.post(
    path="/browser-login/confirm",
    response_model=BrowserAuthStatusResponse,
    summary="Confirm browser login from Telegram bot",
)
async def confirm_browser_login(
    payload: BrowserAuthInternalConfirmRequest,
    svc: Annotated[BrowserAuthService, Depends(get_browser_auth_service)],
) -> BrowserAuthStatusResponse:
    challenge = await svc.confirm(
        token=payload.challenge_token,
        telegram_user={
            "id": payload.telegram_id,
            "username": payload.telegram_username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
        },
    )
    return BrowserAuthStatusResponse.model_validate(svc.build_status_response_payload(challenge))


@router.post(
    path="/uploader-invites/consume",
    response_model=UploaderInviteConsumeResponse,
    summary="Consume uploader invite from Telegram bot",
)
async def consume_uploader_invite(
    payload: UploaderInviteConsumeRequest,
    svc: Annotated[UploaderInviteService, Depends(get_uploader_invite_service)],
) -> UploaderInviteConsumeResponse:
    invite = await svc.consume(
        token=payload.invite_token,
        telegram_user={
            "id": payload.telegram_id,
            "username": payload.telegram_username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
        },
    )
    display_name = (
        " ".join(part for part in [payload.first_name or "", payload.last_name or ""] if part).strip()
        or payload.telegram_username
    )
    return UploaderInviteConsumeResponse(
        invite_token=payload.invite_token,
        status=invite.status,
        approved_display_name=display_name or None,
    )
