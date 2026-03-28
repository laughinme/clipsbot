from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.security import require
from database.relational_db import User
from domain.archive import ArchiveSearchRequest, ArchiveSearchResponse
from service.semantic_search import SemanticSearchService, get_semantic_search_service

router = APIRouter(prefix="/search")


@router.post(
    path="/",
    response_model=ArchiveSearchResponse,
    summary="Semantic archive search",
)
async def search_archive(
    payload: ArchiveSearchRequest,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[SemanticSearchService, Depends(get_semantic_search_service)],
):
    return await svc.search(payload)


@router.get(
    path="/similar/{corpus_item_id}",
    response_model=ArchiveSearchResponse,
    summary="Find corpus items similar to an indexed archive item",
)
async def similar_archive_messages(
    corpus_item_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[SemanticSearchService, Depends(get_semantic_search_service)],
    limit: int = Query(10, ge=1, le=50),
):
    return await svc.similar(corpus_item_id, limit=limit)
