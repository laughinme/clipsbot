from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.common import TimestampModel


class SourceKind(StrEnum):
    TELEGRAM_DESKTOP_EXPORT = "telegram_desktop_export"
    DISCORD = "discord"
    CUSTOM = "custom"


class SourceStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class SyncTriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SyncCoverageKind(StrEnum):
    FULL_SNAPSHOT = "full_snapshot"
    PARTIAL_SAMPLE = "partial_sample"
    INCREMENTAL = "incremental"


class SyncRunStatus(StrEnum):
    CREATED = "created"
    SCANNING = "scanning"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class ArchiveContentType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    SERVICE = "service"
    STICKER = "sticker"
    ANIMATION = "animation"
    UNKNOWN = "unknown"


class ProjectionKind(StrEnum):
    RAW_MULTIMODAL = "raw_multimodal"
    DERIVED_TEXT = "derived_text"


class ProjectionIndexStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


class IndexingJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class EnrichmentKind(StrEnum):
    OCR_RAW = "ocr_raw"
    TRANSCRIPT_RAW = "transcript_raw"
    SUMMARY_TEXT = "summary_text"


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnrichmentRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EnrichmentTriggerKind(StrEnum):
    SYNC = "sync"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SnippetSource(StrEnum):
    TEXT = "text"
    CAPTION = "caption"
    OCR = "ocr"
    TRANSCRIPT = "transcript"
    SUMMARY = "summary"


class CorpusAssetRole(StrEnum):
    PRIMARY = "primary"


class SourceConnectionModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    kind: SourceKind
    slug: str
    display_name: str
    status: SourceStatus
    config_json: dict[str, Any] = Field(default_factory=dict)


class SyncRunModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    source_id: UUID
    trigger_kind: SyncTriggerKind
    coverage_kind: SyncCoverageKind
    status: SyncRunStatus
    cursor: str | None = None
    raw_manifest_object_key: str | None = None
    sample_percent: int | None = None
    include_content_types: list[ArchiveContentType] = Field(default_factory=list)
    exclude_content_types: list[ArchiveContentType] = Field(default_factory=list)
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    unchanged_items: int = 0
    indexed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    queued_items: int = 0
    processing_items: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CorpusAssetModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    corpus_item_id: UUID
    role: CorpusAssetRole
    storage_bucket: str
    object_key: str
    source_relative_path: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    sha256: str
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    play_url: str | None = None
    download_url: str | None = None


class CorpusProjectionModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    corpus_item_id: UUID
    projection_kind: ProjectionKind
    content_hash: str
    qdrant_point_id: str | None = None
    index_status: ProjectionIndexStatus
    index_error: str | None = None
    embedding_model: str | None = None


class CorpusEnrichmentModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    corpus_item_id: UUID
    enrichment_kind: EnrichmentKind
    source_asset_id: UUID | None = None
    source_content_hash: str
    text: str | None = None
    language_code: str | None = None
    provider: str
    provider_model: str | None = None
    status: EnrichmentStatus
    error: str | None = None


class CorpusItemModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    source_id: UUID
    external_key: str
    stable_key: str
    content_hash: str
    content_type: ArchiveContentType
    occurred_at: datetime
    author_external_id: str | None = None
    author_name: str | None = None
    container_external_id: str | None = None
    container_name: str | None = None
    text_content: str | None = None
    caption: str | None = None
    reply_to_external_key: str | None = None
    has_media: bool
    present_in_latest_sync: bool
    first_seen_at: datetime
    last_seen_at: datetime
    last_seen_run_id: UUID | None = None
    source: SourceConnectionModel | None = None
    assets: list[CorpusAssetModel] = Field(default_factory=list)
    projections: list[CorpusProjectionModel] = Field(default_factory=list)
    enrichments: list[CorpusEnrichmentModel] = Field(default_factory=list)


class SourceCreateRequest(BaseModel):
    kind: SourceKind
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(..., min_length=2, max_length=255)
    config_json: dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=255)
    status: SourceStatus | None = None
    config_json: dict[str, Any] | None = None


class SourceListResponse(BaseModel):
    items: list[SourceConnectionModel]


class SourceSyncCreateRequest(BaseModel):
    trigger_kind: SyncTriggerKind = SyncTriggerKind.MANUAL
    coverage_kind: SyncCoverageKind = SyncCoverageKind.FULL_SNAPSHOT
    sample_percent: int | None = Field(default=None, ge=1, le=100)
    include_content_types: list[ArchiveContentType] = Field(default_factory=list)
    exclude_content_types: list[ArchiveContentType] = Field(default_factory=list)


class SyncRunStatusResponse(BaseModel):
    sync_run_id: UUID
    source_id: UUID
    source_display_name: str
    source_kind: SourceKind
    status: SyncRunStatus
    coverage_kind: SyncCoverageKind
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    unchanged_items: int = 0
    queued_items: int = 0
    processing_items: int = 0
    indexed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    progress: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SyncRunListResponse(BaseModel):
    items: list[SyncRunModel]


class EnrichmentRunModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    source_id: UUID | None = None
    sync_run_id: UUID | None = None
    trigger_kind: EnrichmentTriggerKind
    status: EnrichmentRunStatus
    source_ids: list[UUID] = Field(default_factory=list)
    content_types: list[ArchiveContentType] = Field(default_factory=list)
    present_in_latest_sync: bool | None = None
    sample_percent: int | None = None
    total_items: int = 0
    queued_items: int = 0
    processing_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EnrichmentJobModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    enrichment_run_id: UUID
    corpus_item_id: UUID
    enrichment_kind: EnrichmentKind
    status: EnrichmentStatus
    attempts: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None


class EnrichmentRunCreateRequest(BaseModel):
    source_ids: list[UUID] = Field(default_factory=list)
    content_types: list[ArchiveContentType] = Field(default_factory=list)
    present_in_latest_sync: bool | None = None
    sample_percent: int | None = Field(default=None, ge=1, le=100)


class EnrichmentRunStatusResponse(BaseModel):
    enrichment_run_id: UUID
    status: EnrichmentRunStatus
    source_ids: list[UUID] = Field(default_factory=list)
    content_types: list[ArchiveContentType] = Field(default_factory=list)
    present_in_latest_sync: bool | None = None
    sample_percent: int | None = None
    total_items: int = 0
    queued_items: int = 0
    processing_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    progress: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EnrichmentRunListResponse(BaseModel):
    items: list[EnrichmentRunModel]


class ArchiveSearchFilters(BaseModel):
    source_ids: list[UUID] = Field(default_factory=list)
    source_kinds: list[SourceKind] = Field(default_factory=list)
    content_types: list[ArchiveContentType] = Field(default_factory=list)
    author_external_ids: list[str] = Field(default_factory=list)
    container_external_ids: list[str] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    present_in_latest_sync: bool | None = None


class ArchiveSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(20, ge=1, le=50)
    filters: ArchiveSearchFilters = Field(default_factory=ArchiveSearchFilters)


class ArchiveSearchMedia(BaseModel):
    id: UUID
    kind: ArchiveContentType
    mime_type: str | None = None
    original_filename: str | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    play_url: str | None = None
    download_url: str | None = None


class ArchiveSearchResultItem(BaseModel):
    corpus_item_id: UUID
    source_id: UUID
    source_kind: SourceKind
    source_display_name: str
    stable_key: str
    score: float
    content_type: ArchiveContentType
    occurred_at: datetime
    author_external_id: str | None = None
    author_name: str | None = None
    container_external_id: str | None = None
    container_name: str | None = None
    text_preview: str | None = None
    caption: str | None = None
    snippet: str | None = None
    snippet_source: SnippetSource | None = None
    matched_projection_kinds: list[ProjectionKind] = Field(default_factory=list)
    media: ArchiveSearchMedia | None = None


class ArchiveSearchResponse(BaseModel):
    items: list[ArchiveSearchResultItem]
