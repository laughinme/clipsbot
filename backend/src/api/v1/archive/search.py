from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from qdrant_client import models

from core.errors import NotFoundError
from domain.archive import (
    ArchiveSearchFilters,
    ArchiveSearchMedia,
    ArchiveSearchRequest,
    ArchiveSearchResponse,
    ArchiveSearchResultItem,
    ProjectionKind,
    SnippetSource,
    SourceKind,
)
from integrations.embeddings import EmbeddingProvider, get_embedding_provider
from integrations.qdrant import QdrantService, get_qdrant_service
from service.media import MediaStorageService, get_media_storage_service

router = APIRouter(prefix="/search")


def _build_qdrant_filter(filters: ArchiveSearchFilters | None) -> models.Filter | None:
    if not filters:
        return None

    must: list[models.FieldCondition] = []
    if filters.source_ids:
        must.append(models.FieldCondition(key="source_id", match=models.MatchAny(any=[str(item) for item in filters.source_ids])))
    if filters.source_kinds:
        must.append(models.FieldCondition(key="source_kind", match=models.MatchAny(any=[item.value for item in filters.source_kinds])))
    if filters.content_types:
        must.append(models.FieldCondition(key="content_type", match=models.MatchAny(any=[item.value for item in filters.content_types])))
    if filters.author_external_ids:
        must.append(models.FieldCondition(key="author_external_id", match=models.MatchAny(any=filters.author_external_ids)))
    if filters.container_external_ids:
        must.append(models.FieldCondition(key="container_external_id", match=models.MatchAny(any=filters.container_external_ids)))
    if filters.date_from or filters.date_to:
        must.append(
            models.FieldCondition(
                key="occurred_at_unix",
                range=models.Range(
                    gte=int(filters.date_from.timestamp()) if filters.date_from else None,
                    lte=int(filters.date_to.timestamp()) if filters.date_to else None,
                ),
            )
        )
    if filters.present_in_latest_sync is not None:
        must.append(models.FieldCondition(key="present_in_latest_sync", match=models.MatchValue(value=filters.present_in_latest_sync)))

    return models.Filter(must=must) if must else None


def _with_projection_kind(
    base_filter: models.Filter | None,
    projection_kind: ProjectionKind,
) -> models.Filter:
    must = list(base_filter.must) if base_filter and base_filter.must else []
    must.append(models.FieldCondition(key="projection_kind", match=models.MatchValue(value=projection_kind.value)))
    return models.Filter(must=must)


def _payload_string(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    return str(value) if value is not None else None


def _payload_datetime(payload: dict, key: str) -> datetime:
    value = payload.get(key)
    if not value:
        raise NotFoundError(f"Missing {key} in search payload.")
    return datetime.fromisoformat(str(value))


def _payload_source_kind(payload: dict) -> SourceKind:
    return SourceKind(str(payload.get("source_kind") or SourceKind.CUSTOM.value))


def _payload_projection_kind(payload: dict) -> ProjectionKind:
    return ProjectionKind(str(payload.get("projection_kind") or ProjectionKind.RAW_MULTIMODAL.value))


def _payload_snippet_source(payload: dict) -> SnippetSource | None:
    value = payload.get("snippet_source")
    return SnippetSource(str(value)) if value else None


def _build_media(payload: dict, media_storage: MediaStorageService) -> ArchiveSearchMedia | None:
    media_asset_id = payload.get("media_asset_id")
    object_key = payload.get("object_key")
    content_type = payload.get("content_type")
    if not media_asset_id or not object_key or not content_type:
        return None

    download_url = media_storage.create_presigned_download_url(
        bucket=media_storage.archive_bucket,
        key=str(object_key),
    )
    return ArchiveSearchMedia(
        id=UUID(str(media_asset_id)),
        kind=content_type,
        original_filename=None,
        mime_type=None,
        duration_ms=None,
        width=None,
        height=None,
        play_url=download_url,
        download_url=download_url,
    )


def _build_search_item(
    payload: dict,
    *,
    score: float,
    matched_projection_kinds: list[ProjectionKind],
    media_storage: MediaStorageService,
) -> ArchiveSearchResultItem:
    return ArchiveSearchResultItem(
        corpus_item_id=UUID(str(payload["corpus_item_id"])),
        source_id=UUID(str(payload["source_id"])),
        source_kind=_payload_source_kind(payload),
        source_display_name=_payload_string(payload, "source_display_name") or "Unknown Source",
        stable_key=str(payload["stable_key"]),
        score=score,
        content_type=str(payload["content_type"]),
        occurred_at=_payload_datetime(payload, "occurred_at"),
        author_external_id=_payload_string(payload, "author_external_id"),
        author_name=_payload_string(payload, "author_name"),
        container_external_id=_payload_string(payload, "container_external_id"),
        container_name=_payload_string(payload, "container_name"),
        text_preview=_payload_string(payload, "text_preview"),
        caption=_payload_string(payload, "caption"),
        snippet=_payload_string(payload, "snippet"),
        snippet_source=_payload_snippet_source(payload),
        matched_projection_kinds=matched_projection_kinds,
        media=_build_media(payload, media_storage),
    )


def _fuse_ranked_points(
    ranked: list[tuple[ProjectionKind, float, list[models.ScoredPoint]]],
    *,
    limit: int,
    excluded_item_id: UUID | None = None,
) -> list[tuple[dict, float, list[ProjectionKind]]]:
    rrf_k = 60.0
    scores: dict[UUID, float] = {}
    projections: dict[UUID, set[ProjectionKind]] = {}
    payloads: dict[UUID, dict] = {}

    for projection_kind, weight, points in ranked:
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            raw_id = payload.get("corpus_item_id")
            if not raw_id:
                continue
            item_id = UUID(str(raw_id))
            if excluded_item_id is not None and item_id == excluded_item_id:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + weight / (rrf_k + rank)
            projections.setdefault(item_id, set()).add(projection_kind)
            payloads.setdefault(item_id, payload)

    ordered = sorted(scores.items(), key=lambda entry: entry[1], reverse=True)[:limit]
    return [
        (payloads[item_id], score, sorted(projections.get(item_id, set()), key=lambda kind: kind.value))
        for item_id, score in ordered
        if item_id in payloads
    ]


async def _query_projection(
    *,
    qdrant: QdrantService,
    vector: list[float],
    projection_kind: ProjectionKind,
    request: ArchiveSearchRequest | None,
    limit: int,
) -> list[models.ScoredPoint]:
    base_filter = _build_qdrant_filter(request.filters if request else None)
    projection_filter = _with_projection_kind(base_filter, projection_kind)
    return await qdrant.query(vector=vector, limit=limit, query_filter=projection_filter)


@router.post(
    path="",
    response_model=ArchiveSearchResponse,
    summary="Semantic archive search",
)
async def search_archive(
    payload: ArchiveSearchRequest,
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    qdrant: Annotated[QdrantService, Depends(get_qdrant_service)],
    media_storage: Annotated[MediaStorageService, Depends(get_media_storage_service)],
):
    query_vector = await embeddings.embed_query(payload.query)
    candidate_limit = max(payload.limit * 4, 20)
    derived_points, raw_points = await asyncio.gather(
        _query_projection(
            qdrant=qdrant,
            vector=query_vector,
            projection_kind=ProjectionKind.DERIVED_TEXT,
            request=payload,
            limit=candidate_limit,
        ),
        _query_projection(
            qdrant=qdrant,
            vector=query_vector,
            projection_kind=ProjectionKind.RAW_MULTIMODAL,
            request=payload,
            limit=candidate_limit,
        ),
    )

    fused = _fuse_ranked_points(
        [
            (ProjectionKind.DERIVED_TEXT, 2.0, derived_points),
            (ProjectionKind.RAW_MULTIMODAL, 1.0, raw_points),
        ],
        limit=payload.limit,
    )
    return ArchiveSearchResponse(
        items=[
            _build_search_item(
                result_payload,
                score=score,
                matched_projection_kinds=matched_projection_kinds,
                media_storage=media_storage,
            )
            for result_payload, score, matched_projection_kinds in fused
        ]
    )


@router.get(
    path="/similar/{corpus_item_id}",
    response_model=ArchiveSearchResponse,
    summary="Find corpus items similar to an indexed archive item",
)
async def similar_archive_messages(
    corpus_item_id: UUID,
    limit: int = Query(10, ge=1, le=50),
):
    raise NotFoundError(f"Similar search is temporarily unavailable for corpus item {corpus_item_id}; requested limit={limit}.")
