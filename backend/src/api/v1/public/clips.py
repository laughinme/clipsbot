from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from domain.clips import ClipModel, ClipSearchResponse
from service.clips import ClipService, get_clip_service

router = APIRouter(prefix="/clips")


@router.get(
    path="/",
    response_model=ClipSearchResponse,
    summary="List public clips",
)
async def list_public_clips(
    svc: Annotated[ClipService, Depends(get_clip_service)],
    search: str | None = Query(None, description="Search text"),
    limit: int = Query(20, ge=1, le=100),
):
    return await svc.list_public(search=search, limit=limit)


@router.get(
    path="/{clip_id}",
    response_model=ClipModel,
    summary="Get public clip details",
)
async def get_public_clip(
    clip_id: UUID,
    svc: Annotated[ClipService, Depends(get_clip_service)],
):
    return await svc.get_public_by_id(clip_id)


@router.get(
    path="/{clip_id}/audio/{filename}",
    summary="Stream public clip audio with a friendly filename",
)
async def stream_public_clip_audio(
    clip_id: UUID,
    filename: str,
    svc: Annotated[ClipService, Depends(get_clip_service)],
):
    clip, payload = await svc.get_public_audio_payload(clip_id)
    download_name = f"{clip.title}.mp3"
    encoded_name = quote(download_name, safe="")
    return Response(
        content=payload,
        media_type=clip.mime_type or "audio/mpeg",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
            "Cache-Control": "public, max-age=300",
        },
    )
