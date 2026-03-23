from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.security import require
from database.relational_db import User
from domain.clips import ClipModel, ClipPatch
from service.clips import ClipService, get_clip_service

router = APIRouter()


@router.patch(
    path="/",
    response_model=ClipModel,
    summary="Update clip metadata",
)
async def update_clip(
    clip_id: UUID,
    payload: ClipPatch,
    _: Annotated[User, Depends(require("uploader"))],
    svc: Annotated[ClipService, Depends(get_clip_service)],
):
    return await svc.patch_clip(clip_id, payload)
