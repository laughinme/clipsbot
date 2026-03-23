from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from core.security import require
from database.relational_db import User
from service.clips import ClipService, get_clip_service

router = APIRouter()


@router.delete(
    path="/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete clip",
)
async def delete_clip(
    clip_id: UUID,
    _: Annotated[User, Depends(require("uploader"))],
    svc: Annotated[ClipService, Depends(get_clip_service)],
) -> Response:
    await svc.delete_clip(clip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
