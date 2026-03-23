from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.security import require
from database.relational_db import User
from domain.clips import ClipFinalizeRequest, ClipModel
from service.clips import ClipService, get_clip_service

router = APIRouter()


@router.post(
    path="/finalize",
    response_model=ClipModel,
    summary="Finalize clip upload and enqueue processing",
)
async def finalize_upload(
    clip_id: UUID,
    payload: ClipFinalizeRequest,
    _: Annotated[User, Depends(require("uploader"))],
    svc: Annotated[ClipService, Depends(get_clip_service)],
):
    return await svc.finalize_upload(clip_id, payload)
