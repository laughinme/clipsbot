from typing import Annotated

from fastapi import APIRouter, Depends

from core.security import auth_user, require
from database.relational_db import User
from domain.clips import ClipUploadInitRequest, ClipUploadInitResponse
from service.clips import ClipService, get_clip_service

router = APIRouter()


@router.post(
    path="/upload-init",
    response_model=ClipUploadInitResponse,
    summary="Create draft clip and presigned upload URL",
)
async def upload_init(
    payload: ClipUploadInitRequest,
    _: Annotated[User, Depends(require("uploader"))],
    uploader: Annotated[User, Depends(auth_user)],
    svc: Annotated[ClipService, Depends(get_clip_service)],
):
    return await svc.init_upload(payload, uploader)
