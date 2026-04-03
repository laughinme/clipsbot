from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from database.relational_db import SourceConnection, SyncRun
from domain.archive import ArchiveContentType, CorpusAssetRole, ProjectionIndexStatus, ProjectionKind, SourceKind


@dataclass(slots=True)
class NormalizedAsset:
    role: CorpusAssetRole
    local_path: Path
    source_relative_path: str | None
    original_filename: str | None
    mime_type: str | None
    file_size_bytes: int | None
    content_fingerprint: str
    sha256: str | None
    duration_ms: int | None
    width: int | None
    height: int | None


@dataclass(slots=True)
class NormalizedSourceItem:
    external_key: str
    stable_key: str
    content_hash: str
    content_type: ArchiveContentType
    occurred_at: Any
    author_external_id: str | None
    author_name: str | None
    container_external_id: str | None
    container_name: str | None
    text_content: str | None
    caption: str | None
    reply_to_external_key: str | None
    has_media: bool
    asset: NormalizedAsset | None
    projection_kind: ProjectionKind
    projection_status: ProjectionIndexStatus
    projection_error: str | None


@dataclass(slots=True)
class ScannedSyncRun:
    manifest_path: Path
    items: list[NormalizedSourceItem]


@dataclass(slots=True)
class ScannedSyncBatch:
    manifest_path: Path
    items: list[NormalizedSourceItem]
    next_cursor: str | None = None


class SourceAdapter(ABC):
    kind: SourceKind

    @abstractmethod
    def validate_source_config(self, config_json: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def scan_sync_run(self, *, source: SourceConnection, sync_run: SyncRun) -> ScannedSyncRun:
        raise NotImplementedError

    async def iter_sync_run_batches(
        self,
        *,
        source: SourceConnection,
        sync_run: SyncRun,
    ) -> AsyncIterator[ScannedSyncBatch]:
        scanned = await self.scan_sync_run(source=source, sync_run=sync_run)
        yield ScannedSyncBatch(manifest_path=scanned.manifest_path, items=scanned.items)

    @abstractmethod
    def normalize_item(self, *, source: SourceConnection, parsed_message: Any, root_path: Path) -> NormalizedSourceItem | None:
        raise NotImplementedError

    @abstractmethod
    def resolve_assets(self, *, root_path: Path, parsed_message: Any) -> NormalizedAsset | None:
        raise NotImplementedError

    @abstractmethod
    def build_external_key(self, *, parsed_message: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_content_hash(self, *, normalized_item: NormalizedSourceItem) -> str:
        raise NotImplementedError


class SourceAdapterRegistry:
    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self._adapters = {adapter.kind.value: adapter for adapter in adapters}

    def get(self, kind: str) -> SourceAdapter:
        try:
            return self._adapters[kind]
        except KeyError as exc:
            raise RuntimeError(f"Unsupported source adapter kind: {kind}") from exc
