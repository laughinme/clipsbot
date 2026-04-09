from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import models

from core.config import Settings
from core.errors import NotFoundError
from database.relational_db import (
    CorpusAsset,
    CorpusItem,
    CorpusItemInterface,
    CorpusProjection,
    CorpusProjectionInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    UoW,
)
from domain.archive import (
    ArchiveSearchMedia,
    ArchiveSearchRequest,
    ArchiveSearchResponse,
    ArchiveSearchResultItem,
    EnrichmentKind,
    ProjectionIndexStatus,
    ProjectionKind,
    SnippetSource,
)
from integrations.embeddings import EmbeddingProvider
from integrations.qdrant import QdrantService
from service.media import MediaStorageService


class SemanticSearchService:
    def __init__(
        self,
        *,
        uow: UoW,
        source_repo: SourceConnectionInterface,
        corpus_item_repo: CorpusItemInterface,
        corpus_projection_repo: CorpusProjectionInterface,
        indexing_job_repo: IndexingJobInterface,
        embeddings: EmbeddingProvider,
        qdrant: QdrantService,
        media_storage: MediaStorageService,
        settings: Settings,
    ) -> None:
        self.uow = uow
        self.source_repo = source_repo
        self.corpus_item_repo = corpus_item_repo
        self.corpus_projection_repo = corpus_projection_repo
        self.indexing_job_repo = indexing_job_repo
        self.embeddings = embeddings
        self.qdrant = qdrant
        self.media_storage = media_storage
        self.settings = settings

    async def _report_progress(
        self,
        callback: Callable[[str, str | None], Awaitable[None]] | None,
        stage: str,
        detail: str | None = None,
    ) -> None:
        if callback is not None:
            await callback(stage, detail)

    def _preview(self, value: str | None, limit: int = 280) -> str | None:
        if not value:
            return None
        normalized = " ".join(value.split())
        return normalized[: limit - 1] + "…" if len(normalized) > limit else normalized

    def _primary_asset(self, item: CorpusItem) -> CorpusAsset | None:
        return next((asset for asset in item.assets if asset.role == "primary"), None)

    def _projection(self, item: CorpusItem, kind: ProjectionKind) -> CorpusProjection | None:
        return next((projection for projection in item.projections if projection.projection_kind == kind.value), None)

    def _enrichment_text(self, item: CorpusItem, kind: EnrichmentKind) -> str | None:
        enrichment = next((entry for entry in item.enrichments if entry.enrichment_kind == kind.value), None)
        if enrichment is None or enrichment.status != "completed":
            return None
        return enrichment.text

    def _build_derived_text(self, item: CorpusItem) -> str:
        source_name = item.source.display_name if item.source is not None else "Unknown Source"
        container = item.container_name or item.container_external_id or "Unknown container"
        author = item.author_name or item.author_external_id or "Unknown author"
        parts = [
            f"type: {item.content_type}",
            f"source: {source_name} / {container}",
            f"author: {author}",
            f"message_text: {item.text_content or ''}",
            f"caption: {item.caption or ''}",
            f"ocr_text: {self._enrichment_text(item, EnrichmentKind.OCR_RAW) or ''}",
            f"transcript: {self._enrichment_text(item, EnrichmentKind.TRANSCRIPT_RAW) or ''}",
            f"summary: {self._enrichment_text(item, EnrichmentKind.SUMMARY_TEXT) or ''}",
        ]
        return "\n".join(part for part in parts if part.split(":", 1)[-1].strip()).strip()

    def _pick_snippet(self, item: CorpusItem) -> tuple[str | None, SnippetSource | None]:
        summary = self._preview(self._enrichment_text(item, EnrichmentKind.SUMMARY_TEXT))
        if summary:
            return summary, SnippetSource.SUMMARY
        transcript = self._preview(self._enrichment_text(item, EnrichmentKind.TRANSCRIPT_RAW))
        if transcript:
            return transcript, SnippetSource.TRANSCRIPT
        ocr = self._preview(self._enrichment_text(item, EnrichmentKind.OCR_RAW))
        if ocr:
            return ocr, SnippetSource.OCR
        if item.caption:
            return self._preview(item.caption), SnippetSource.CAPTION
        if item.text_content:
            return self._preview(item.text_content), SnippetSource.TEXT
        return None, None

    def _media_urls(self, media_asset: CorpusAsset | None) -> tuple[str | None, str | None]:
        if media_asset is None:
            return None, None
        download_url = self.media_storage.create_presigned_download_url(
            bucket=media_asset.storage_bucket,
            key=media_asset.object_key,
        )
        return download_url, download_url

    def _build_qdrant_filter(self, request: ArchiveSearchRequest | None = None):
        must: list[models.FieldCondition] = []
        filters = request.filters if request else None
        if not filters:
            return None

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
        self,
        base_filter: models.Filter | None,
        projection_kind: ProjectionKind,
    ) -> models.Filter:
        must = list(base_filter.must) if base_filter and base_filter.must else []
        must.append(
            models.FieldCondition(
                key="projection_kind",
                match=models.MatchValue(value=projection_kind.value),
            )
        )
        return models.Filter(must=must)

    def _build_point_id(self, *, stable_key: str, projection_kind: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"corpus:{stable_key}:{projection_kind}"))

    async def build_point_payload(
        self,
        item: CorpusItem,
        *,
        projection_kind: ProjectionKind,
        source_display_name: str | None = None,
    ) -> dict[str, object]:
        media_asset = self._primary_asset(item)
        snippet, snippet_source = self._pick_snippet(item)
        source = item.source
        return {
            "corpus_item_id": str(item.id),
            "projection_kind": projection_kind.value,
            "source_id": str(item.source_id),
            "source_kind": source.kind if source is not None else None,
            "source_display_name": source_display_name or (source.display_name if source is not None else None),
            "stable_key": item.stable_key,
            "content_type": item.content_type,
            "occurred_at": item.occurred_at.isoformat(),
            "occurred_at_unix": int(item.occurred_at.timestamp()),
            "author_external_id": item.author_external_id,
            "author_name": item.author_name,
            "container_external_id": item.container_external_id,
            "container_name": item.container_name,
            "present_in_latest_sync": item.present_in_latest_sync,
            "text_preview": self._preview(item.text_content),
            "caption": self._preview(item.caption),
            "snippet": snippet,
            "snippet_source": snippet_source.value if snippet_source is not None else None,
            "media_asset_id": str(media_asset.id) if media_asset else None,
            "object_key": media_asset.object_key if media_asset else None,
            "source_relative_path": media_asset.source_relative_path if media_asset else None,
        }

    async def process_indexing_job(
        self,
        job_id: UUID | str,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> None:
        snapshot = await self.indexing_job_repo.get_processing_snapshot(job_id)
        if (
            snapshot is not None
            and snapshot.status != "done"
            and snapshot.projection.projection_kind == ProjectionKind.RAW_MULTIMODAL.value
        ):
            await self._report_progress(progress_callback, "job_loaded", str(job_id))
            await self._process_single_job_fast(snapshot, progress_callback=progress_callback)
            return

        job = await self.indexing_job_repo.get_by_id(job_id, include_enrichments=False)
        if job is None or job.status == "done":
            return
        await self._report_progress(progress_callback, "job_loaded", str(job_id))

        projection = job.projection
        if projection is None:
            raise NotFoundError("Corpus projection not found for indexing job.")
        item = projection.corpus_item
        if item is None:
            raise NotFoundError("Corpus item not found for indexing job.")
        if projection.projection_kind == ProjectionKind.DERIVED_TEXT.value:
            full_item = await self.corpus_item_repo.get_by_id(item.id)
            if full_item is None:
                raise NotFoundError("Corpus item not found for derived indexing job.")
            item = full_item
            projection = next(
                (candidate for candidate in full_item.projections if candidate.id == projection.id),
                projection,
            )
        primary_asset = self._primary_asset(item)

        batch_jobs = [job]
        if job.status != "processing" or job.started_at is None:
            job.status = "processing"
            job.attempts += 1
            job.started_at = datetime.now(timezone.utc)
        projection.index_status = ProjectionIndexStatus.PROCESSING.value
        projection.index_error = None

        if self._is_text_batch_candidate(projection=projection, item=item):
            additional_jobs = await self.indexing_job_repo.claim_additional_text_batch(
                projection_kind=projection.projection_kind,
                limit=max(self.settings.TEXT_EMBED_BATCH_SIZE - 1, 0),
                exclude_job_ids=[job.id],
                raw_text_only=projection.projection_kind == ProjectionKind.RAW_MULTIMODAL.value,
            )
            for extra_job in additional_jobs:
                if extra_job.projection is None or extra_job.projection.corpus_item is None:
                    continue
                extra_job.projection.index_status = ProjectionIndexStatus.PROCESSING.value
                extra_job.projection.index_error = None
                batch_jobs.append(extra_job)

        batch_job_ids = [batch_job.id for batch_job in batch_jobs]
        await self._report_progress(progress_callback, "db_prepare_commit", f"batch={len(batch_job_ids)}")
        await self.uow.commit()
        await self._report_progress(progress_callback, "job_ready", f"batch={len(batch_job_ids)}")

        try:
            if len(batch_jobs) > 1 or self._is_text_batch_candidate(projection=projection, item=item):
                await self._process_text_batch(batch_jobs, progress_callback=progress_callback)
            else:
                await self._process_single_job(
                    job,
                    projection=projection,
                    item=item,
                    primary_asset=primary_asset,
                    progress_callback=progress_callback,
                )
        except Exception as exc:
            await self.uow.session.rollback()
            await self._report_progress(progress_callback, "failed", str(exc))
            failed_jobs = await self.indexing_job_repo.list_by_ids(batch_job_ids)
            for failed_job in failed_jobs:
                if failed_job.projection is None:
                    continue
                failed_projection = failed_job.projection
                failed_projection.index_status = ProjectionIndexStatus.FAILED.value
                failed_projection.index_error = str(exc)
                failed_job.status = "failed"
                failed_job.last_error = str(exc)
                failed_job.completed_at = datetime.now(timezone.utc)
            await self.uow.commit()
            raise

    def _is_text_batch_candidate(self, *, projection: CorpusProjection, item: CorpusItem) -> bool:
        if projection.projection_kind == ProjectionKind.DERIVED_TEXT.value:
            return True
        return (
            projection.projection_kind == ProjectionKind.RAW_MULTIMODAL.value
            and item.content_type == "text"
        )

    def _build_projection_document(
        self,
        *,
        projection: CorpusProjection,
        item: CorpusItem,
        primary_asset: CorpusAsset | None,
    ) -> str:
        if projection.projection_kind == ProjectionKind.DERIVED_TEXT.value:
            return self._build_derived_text(item)
        return self.embeddings.build_document_text(item, primary_asset)

    async def _process_text_batch(
        self,
        jobs: list,
        *,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> None:
        indexed_at = datetime.now(timezone.utc)
        documents: list[str] = []
        entries: list[tuple] = []

        for job in jobs:
            projection = job.projection
            item = projection.corpus_item if projection is not None else None
            if projection is None or item is None:
                raise NotFoundError("Corpus projection not found for indexing job.")
            primary_asset = self._primary_asset(item)
            documents.append(
                self._build_projection_document(
                    projection=projection,
                    item=item,
                    primary_asset=primary_asset,
                )
            )
            entries.append((job, projection, item))

        await self._report_progress(progress_callback, "vertex_request", f"text_batch={len(entries)}")
        vectors = await self.embeddings.embed_documents(documents)
        if len(vectors) != len(entries):
            raise RuntimeError("Embedding batch result size does not match requested documents.")

        for (job, projection, item), vector in zip(entries, vectors, strict=True):
            if len(vector) != self.settings.EMBEDDING_VECTOR_SIZE:
                raise RuntimeError(f"Unexpected embedding size {len(vector)}")
            projection_kind = ProjectionKind(projection.projection_kind)
            point_id = self._build_point_id(
                stable_key=item.stable_key,
                projection_kind=projection.projection_kind,
            )
            payload = await self.build_point_payload(item, projection_kind=projection_kind)
            await self._report_progress(progress_callback, "qdrant_upsert")
            await self.qdrant.upsert_point(point_id=point_id, vector=vector, payload=payload)
            projection.qdrant_point_id = point_id
            projection.index_status = ProjectionIndexStatus.INDEXED.value
            projection.index_error = None
            projection.embedding_model = (
                self.settings.GEMINI_EMBEDDING_MODEL
                if self.settings.EMBEDDING_PROVIDER == "vertex"
                else f"stub:{self.settings.EMBEDDING_VECTOR_SIZE}"
            )
            job.status = "done"
            job.completed_at = indexed_at
            job.last_error = None

        await self._report_progress(progress_callback, "db_commit")
        await self.uow.commit()

    async def _process_single_job_fast(
        self,
        job,
        *,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> None:
        projection = job.projection
        item = projection.corpus_item
        primary_asset = self._primary_asset(item)
        try:
            media_bytes = None
            if primary_asset is not None:
                await self._report_progress(
                    progress_callback,
                    "read_asset",
                    primary_asset.source_relative_path or item.stable_key,
                )
                media_bytes = await self._read_asset_bytes(primary_asset)
            vector = await self.embeddings.embed_message(
                item,
                primary_asset,
                media_bytes=media_bytes,
                progress_callback=progress_callback,
            )
            if len(vector) != self.settings.EMBEDDING_VECTOR_SIZE:
                raise RuntimeError(f"Unexpected embedding size {len(vector)}")

            point_id = self._build_point_id(
                stable_key=item.stable_key,
                projection_kind=projection.projection_kind,
            )
            payload = await self.build_point_payload(
                item,
                projection_kind=ProjectionKind(projection.projection_kind),
            )
            await self._report_progress(progress_callback, "qdrant_upsert", item.stable_key)
            await self.qdrant.upsert_point(point_id=point_id, vector=vector, payload=payload)
            await self._report_progress(progress_callback, "db_commit", item.stable_key)
            await self.indexing_job_repo.mark_done_fast(
                job_id=job.id,
                projection_id=projection.id,
                point_id=point_id,
                embedding_model=(
                    self.settings.GEMINI_EMBEDDING_MODEL
                    if self.settings.EMBEDDING_PROVIDER == "vertex"
                    else f"stub:{self.settings.EMBEDDING_VECTOR_SIZE}"
                ),
            )
            await self.uow.commit()
        except Exception as exc:
            await self.uow.session.rollback()
            await self._report_progress(progress_callback, "failed", str(exc))
            await self.indexing_job_repo.mark_failed_fast(
                job_id=job.id,
                projection_id=projection.id,
                error=str(exc),
            )
            await self.uow.commit()
            raise

    async def _process_single_job(
        self,
        job,
        *,
        projection: CorpusProjection,
        item: CorpusItem,
        primary_asset: CorpusAsset | None,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> None:
        if projection.projection_kind == ProjectionKind.DERIVED_TEXT.value:
            document_text = self._build_derived_text(item)
            await self._report_progress(progress_callback, "vertex_request", f"derived_text:{item.stable_key}")
            vector = await self.embeddings.embed_text(document_text)
        else:
            media_bytes = None
            if primary_asset is not None:
                await self._report_progress(
                    progress_callback,
                    "read_asset",
                    primary_asset.source_relative_path or item.stable_key,
                )
                media_bytes = await self._read_asset_bytes(primary_asset)
            vector = await self.embeddings.embed_message(
                item,
                primary_asset,
                media_bytes=media_bytes,
                progress_callback=progress_callback,
            )

        if len(vector) != self.settings.EMBEDDING_VECTOR_SIZE:
            raise RuntimeError(f"Unexpected embedding size {len(vector)}")

        projection_kind = ProjectionKind(projection.projection_kind)
        point_id = self._build_point_id(
            stable_key=item.stable_key,
            projection_kind=projection.projection_kind,
        )
        payload = await self.build_point_payload(item, projection_kind=projection_kind)
        await self._report_progress(progress_callback, "qdrant_upsert", item.stable_key)
        await self.qdrant.upsert_point(point_id=point_id, vector=vector, payload=payload)

        projection.qdrant_point_id = point_id
        projection.index_status = ProjectionIndexStatus.INDEXED.value
        projection.index_error = None
        projection.embedding_model = (
            self.settings.GEMINI_EMBEDDING_MODEL
            if self.settings.EMBEDDING_PROVIDER == "vertex"
            else f"stub:{self.settings.EMBEDDING_VECTOR_SIZE}"
        )
        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = None
        await self._report_progress(progress_callback, "db_commit", item.stable_key)
        await self.uow.commit()

    async def _read_asset_bytes(self, asset: CorpusAsset) -> bytes:
        return await asyncio.to_thread(
            self.media_storage.get_object_bytes,
            bucket=asset.storage_bucket,
            key=asset.object_key,
        )

    def _build_search_item(
        self,
        item: CorpusItem,
        *,
        score: float,
        matched_projection_kinds: list[ProjectionKind],
    ) -> ArchiveSearchResultItem:
        source = item.source
        media_asset = self._primary_asset(item)
        play_url, download_url = self._media_urls(media_asset)
        snippet, snippet_source = self._pick_snippet(item)
        media = None
        if media_asset is not None:
            media = ArchiveSearchMedia(
                id=media_asset.id,
                kind=item.content_type,
                mime_type=media_asset.mime_type,
                original_filename=media_asset.original_filename,
                duration_ms=media_asset.duration_ms,
                width=media_asset.width,
                height=media_asset.height,
                play_url=play_url,
                download_url=download_url,
            )

        return ArchiveSearchResultItem(
            corpus_item_id=item.id,
            source_id=item.source_id,
            source_kind=source.kind if source is not None else "custom",
            source_display_name=source.display_name if source is not None else "Unknown Source",
            stable_key=item.stable_key,
            score=score,
            content_type=item.content_type,
            occurred_at=item.occurred_at,
            author_external_id=item.author_external_id,
            author_name=item.author_name,
            container_external_id=item.container_external_id,
            container_name=item.container_name,
            text_preview=self._preview(item.text_content),
            caption=self._preview(item.caption),
            snippet=snippet,
            snippet_source=snippet_source,
            matched_projection_kinds=matched_projection_kinds,
            media=media,
        )

    async def _query_projection(
        self,
        *,
        vector: list[float],
        projection_kind: ProjectionKind,
        request: ArchiveSearchRequest | None,
        limit: int,
    ) -> list[models.ScoredPoint]:
        base_filter = self._build_qdrant_filter(request)
        projection_filter = self._with_projection_kind(base_filter, projection_kind)
        return await self.qdrant.query(vector=vector, limit=limit, query_filter=projection_filter)

    def _fuse_ranked_points(
        self,
        ranked: list[tuple[ProjectionKind, float, list[models.ScoredPoint]]],
        *,
        limit: int,
        excluded_item_id: UUID | None = None,
    ) -> list[tuple[UUID, float, list[ProjectionKind]]]:
        rrf_k = 60.0
        scores: dict[UUID, float] = {}
        projections: dict[UUID, set[ProjectionKind]] = {}
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

        ordered = sorted(scores.items(), key=lambda entry: entry[1], reverse=True)[:limit]
        return [(item_id, score, sorted(projections.get(item_id, set()), key=lambda kind: kind.value)) for item_id, score in ordered]

    async def search(self, request: ArchiveSearchRequest) -> ArchiveSearchResponse:
        query_vector = await self.embeddings.embed_query(request.query)
        candidate_limit = max(request.limit * 4, 20)
        derived_points, raw_points = await asyncio.gather(
            self._query_projection(
                vector=query_vector,
                projection_kind=ProjectionKind.DERIVED_TEXT,
                request=request,
                limit=candidate_limit,
            ),
            self._query_projection(
                vector=query_vector,
                projection_kind=ProjectionKind.RAW_MULTIMODAL,
                request=request,
                limit=candidate_limit,
            ),
        )

        fused = self._fuse_ranked_points(
            [
                (ProjectionKind.DERIVED_TEXT, 2.0, derived_points),
                (ProjectionKind.RAW_MULTIMODAL, 1.0, raw_points),
            ],
            limit=request.limit,
        )
        item_ids = [item_id for item_id, _, _ in fused]
        items = await self.corpus_item_repo.list_by_ids(item_ids)
        item_map = {item.id: item for item in items}
        return ArchiveSearchResponse(
            items=[
                self._build_search_item(item_map[item_id], score=score, matched_projection_kinds=matched_projection_kinds)
                for item_id, score, matched_projection_kinds in fused
                if item_id in item_map
            ]
        )

    async def similar(self, corpus_item_id: UUID | str, limit: int) -> ArchiveSearchResponse:
        item = await self.corpus_item_repo.get_by_id(corpus_item_id)
        if item is None:
            raise NotFoundError("Corpus item not found.")

        projection_vectors: list[tuple[ProjectionKind, float, list[float]]] = []
        for projection_kind, weight in ((ProjectionKind.DERIVED_TEXT, 2.0), (ProjectionKind.RAW_MULTIMODAL, 1.0)):
            projection = self._projection(item, projection_kind)
            if projection is None or not projection.qdrant_point_id:
                continue
            vector = await self.qdrant.get_point_vector(projection.qdrant_point_id)
            projection_vectors.append((projection_kind, weight, vector))

        if not projection_vectors:
            raise NotFoundError("Indexed projection not found for corpus item.")

        query_lists = await asyncio.gather(
            *(
                self._query_projection(
                    vector=vector,
                    projection_kind=projection_kind,
                    request=None,
                    limit=max(limit * 4, 20),
                )
                for projection_kind, _, vector in projection_vectors
            )
        )
        fused = self._fuse_ranked_points(
            [
                (projection_kind, weight, points)
                for (projection_kind, weight, _), points in zip(projection_vectors, query_lists, strict=True)
            ],
            limit=limit,
            excluded_item_id=item.id,
        )
        item_ids = [item_id for item_id, _, _ in fused]
        items = await self.corpus_item_repo.list_by_ids(item_ids)
        item_map = {candidate.id: candidate for candidate in items}
        return ArchiveSearchResponse(
            items=[
                self._build_search_item(item_map[item_id], score=score, matched_projection_kinds=matched_projection_kinds)
                for item_id, score, matched_projection_kinds in fused
                if item_id in item_map
            ]
        )

    async def get_item(self, corpus_item_id: UUID | str) -> ArchiveSearchResultItem:
        item = await self.corpus_item_repo.get_by_id(corpus_item_id)
        if item is None:
            raise NotFoundError("Corpus item not found.")

        matched_projection_kinds = [
            ProjectionKind(projection.projection_kind)
            for projection in item.projections
            if projection.index_status == ProjectionIndexStatus.INDEXED.value
        ]
        return self._build_search_item(
            item,
            score=1.0,
            matched_projection_kinds=matched_projection_kinds,
        )
