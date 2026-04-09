from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from domain.archive import ArchiveSearchItemResponse
from service.semantic_search import SemanticSearchService, get_semantic_search_service

router = APIRouter(prefix="/items")


@router.get(
    path="/{corpus_item_id}",
    response_model=ArchiveSearchItemResponse,
    summary="Get one archive item by corpus id",
)
async def get_archive_item(
    corpus_item_id: UUID,
    svc: Annotated[SemanticSearchService, Depends(get_semantic_search_service)],
):
    return ArchiveSearchItemResponse(item=await svc.get_item(corpus_item_id))
