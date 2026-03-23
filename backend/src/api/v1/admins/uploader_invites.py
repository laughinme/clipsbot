from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.security import auth_user, require
from database.relational_db import User
from domain.users import UploaderInviteCreateResponse, UploaderInviteModel
from service.users import UploaderInviteService, get_uploader_invite_service

router = APIRouter(prefix="/uploader-invites")


@router.get(
    path="/",
    response_model=list[UploaderInviteModel],
    summary="List recent uploader invite links",
)
async def list_uploader_invites(
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[UploaderInviteService, Depends(get_uploader_invite_service)],
    limit: int = Query(20, ge=1, le=100),
):
    return await svc.list_recent(limit=limit)


@router.post(
    path="/",
    response_model=UploaderInviteCreateResponse,
    summary="Create uploader invite link",
)
async def create_uploader_invite(
    _: Annotated[User, Depends(require("admin"))],
    current_user: Annotated[User, Depends(auth_user)],
    svc: Annotated[UploaderInviteService, Depends(get_uploader_invite_service)],
):
    return await svc.create(current_user)


@router.post(
    path="/{invite_id}/revoke",
    response_model=UploaderInviteModel,
    summary="Revoke uploader invite link",
)
async def revoke_uploader_invite(
    invite_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[UploaderInviteService, Depends(get_uploader_invite_service)],
):
    return await svc.revoke(invite_id)
