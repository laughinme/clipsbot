from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.security import require
from database.relational_db import User
from domain.clips import ClipSearchResponse
from service.clips import ClipService, get_clip_service

router = APIRouter()


@router.get(
    path="/",
    response_model=ClipSearchResponse,
    summary="List clips for admins and uploaders",
)
async def list_clips(
    _: Annotated[User, Depends(require("uploader"))],
    svc: Annotated[ClipService, Depends(get_clip_service)],
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    return await svc.list_admin(search=search, limit=limit)
