from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from core.config import Settings
from core.errors import BadRequestError
from database.relational_db import SourceConnection, SyncRun
from domain.archive import ArchiveContentType, CorpusAssetRole, ProjectionIndexStatus, ProjectionKind, SourceKind
from service.archive_imports.parser import ParsedTelegramMessage, parse_message

from .base import NormalizedAsset, NormalizedSourceItem, ScannedSyncBatch, ScannedSyncRun, SourceAdapter


class TelegramDesktopExportAdapter(SourceAdapter):
    kind = SourceKind.TELEGRAM_DESKTOP_EXPORT
    _NORMALIZE_BATCH_SIZE = 128

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_source_config(self, config_json: dict[str, Any]) -> None:
        export_path = str(config_json.get("export_path") or "").strip()
        if not export_path:
            raise BadRequestError("Telegram Desktop export source requires config_json.export_path.")
        self._resolve_manifest_path(export_path)

    def _normalize_content_types(self, values: str | None) -> set[str]:
        return {part.strip() for part in (values or "").split(",") if part.strip()}

    def _normalize_input_path(self, raw_path: str) -> Path:
        requested = Path(raw_path).expanduser()
        if self.settings.ARCHIVE_IMPORT_HOST_ROOT and self.settings.ARCHIVE_IMPORT_CONTAINER_ROOT:
            host_root = Path(self.settings.ARCHIVE_IMPORT_HOST_ROOT).expanduser()
            try:
                relative = requested.resolve().relative_to(host_root.resolve())
                requested = Path(self.settings.ARCHIVE_IMPORT_CONTAINER_ROOT) / relative
            except Exception:
                pass

        resolved = requested.resolve()
        allowed_roots = self.settings.archive_import_allowed_roots
        if allowed_roots and not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise BadRequestError("Archive source path is outside the allowed roots.")
        return resolved

    def _resolve_manifest_path(self, source_path: str) -> tuple[Path, Path]:
        root = self._normalize_input_path(source_path)
        manifest = root / "result.json"
        if root.is_file():
            manifest = root
            root = root.parent
        if not manifest.exists():
            raise BadRequestError(f"Could not find result.json in {source_path}")
        return root, manifest

    def _should_include_by_sample(self, *, external_key: str, sample_percent: int | None) -> bool:
        if not sample_percent or sample_percent >= 100:
            return True
        bucket = int(hashlib.sha256(external_key.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < sample_percent

    def build_external_key(self, *, parsed_message: ParsedTelegramMessage) -> str:
        return f"{parsed_message.chat_id or 'none'}:{parsed_message.telegram_message_id}"

    def _build_stable_key(self, *, parsed_message: ParsedTelegramMessage) -> str:
        return f"telegram:{parsed_message.chat_id or 'none'}:{parsed_message.telegram_message_id}"

    def resolve_assets(self, *, root_path: Path, parsed_message: ParsedTelegramMessage) -> NormalizedAsset | None:
        if not parsed_message.source_relative_path:
            return None

        local_path = (root_path / parsed_message.source_relative_path).resolve()
        if not local_path.exists():
            return None
        stat = local_path.stat()
        content_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "path": str(local_path),
                    "size": parsed_message.file_size_bytes or stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "filename": parsed_message.original_filename,
                    "mime_type": parsed_message.mime_type,
                    "duration_ms": parsed_message.duration_ms,
                    "width": parsed_message.width,
                    "height": parsed_message.height,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        return NormalizedAsset(
            role=CorpusAssetRole.PRIMARY,
            local_path=local_path,
            source_relative_path=parsed_message.source_relative_path,
            original_filename=parsed_message.original_filename,
            mime_type=parsed_message.mime_type,
            file_size_bytes=parsed_message.file_size_bytes,
            content_fingerprint=content_fingerprint,
            sha256=None,
            duration_ms=parsed_message.duration_ms,
            width=parsed_message.width,
            height=parsed_message.height,
        )

    def build_content_hash(self, *, normalized_item: NormalizedSourceItem) -> str:
        payload = {
            "stable_key": normalized_item.stable_key,
            "content_type": normalized_item.content_type.value,
            "occurred_at": normalized_item.occurred_at.isoformat(),
            "author_external_id": normalized_item.author_external_id,
            "author_name": normalized_item.author_name,
            "container_external_id": normalized_item.container_external_id,
            "container_name": normalized_item.container_name,
            "text_content": normalized_item.text_content,
            "caption": normalized_item.caption,
            "reply_to_external_key": normalized_item.reply_to_external_key,
            "has_media": normalized_item.has_media,
            "asset": {
                "fingerprint": normalized_item.asset.content_fingerprint if normalized_item.asset else None,
                "mime_type": normalized_item.asset.mime_type if normalized_item.asset else None,
                "filename": normalized_item.asset.original_filename if normalized_item.asset else None,
                "duration_ms": normalized_item.asset.duration_ms if normalized_item.asset else None,
                "width": normalized_item.asset.width if normalized_item.asset else None,
                "height": normalized_item.asset.height if normalized_item.asset else None,
            },
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def normalize_item(self, *, source: SourceConnection, parsed_message: ParsedTelegramMessage, root_path: Path) -> NormalizedSourceItem | None:
        del source
        external_key = self.build_external_key(parsed_message=parsed_message)
        stable_key = self._build_stable_key(parsed_message=parsed_message)
        asset = self.resolve_assets(root_path=root_path, parsed_message=parsed_message)

        projection_status = parsed_message.index_status
        projection_error = parsed_message.index_error
        if parsed_message.message_type != ArchiveContentType.TEXT and parsed_message.has_media and asset is None:
            projection_status = ProjectionIndexStatus.SKIPPED
            projection_error = "media_missing_from_export"

        item = NormalizedSourceItem(
            external_key=external_key,
            stable_key=stable_key,
            content_hash="",
            content_type=parsed_message.message_type,
            occurred_at=parsed_message.timestamp,
            author_external_id=str(parsed_message.author_telegram_id) if parsed_message.author_telegram_id is not None else None,
            author_name=parsed_message.author_name,
            container_external_id=str(parsed_message.chat_id) if parsed_message.chat_id is not None else None,
            container_name=parsed_message.chat_title,
            text_content=parsed_message.text_content,
            caption=parsed_message.caption,
            reply_to_external_key=(
                f"{parsed_message.chat_id or 'none'}:{parsed_message.reply_to_message_id}"
                if parsed_message.reply_to_message_id is not None
                else None
            ),
            has_media=parsed_message.has_media,
            asset=asset,
            projection_kind=ProjectionKind.RAW_MULTIMODAL,
            projection_status=projection_status,
            projection_error=projection_error,
        )
        item.content_hash = self.build_content_hash(normalized_item=item)
        return item

    async def scan_sync_run(self, *, source: SourceConnection, sync_run: SyncRun) -> ScannedSyncRun:
        items: list[NormalizedSourceItem] = []
        manifest_path: Path | None = None
        async for batch in self.iter_sync_run_batches(source=source, sync_run=sync_run):
            items.extend(batch.items)
            manifest_path = batch.manifest_path
        if manifest_path is None:
            _, manifest_path = self._resolve_manifest_path(str(source.config_json.get("export_path") or "").strip())
        return ScannedSyncRun(manifest_path=manifest_path, items=items)

    async def iter_sync_run_batches(self, *, source: SourceConnection, sync_run: SyncRun):
        export_path = str(source.config_json.get("export_path") or "").strip()
        root_path, manifest_path = self._resolve_manifest_path(export_path)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        cursor_offset = 0
        if sync_run.cursor:
            try:
                cursor_offset = max(int(sync_run.cursor), 0)
            except ValueError:
                cursor_offset = 0

        include_types = self._normalize_content_types(sync_run.include_content_types)
        exclude_types = self._normalize_content_types(sync_run.exclude_content_types)
        raw_messages = payload.get("messages", [])
        chat_id = payload.get("id")
        chat_title = payload.get("name")

        pending_batch: list[ParsedTelegramMessage] = []
        pending_next_cursor: int | None = None

        async def _flush_pending() -> list[NormalizedSourceItem]:
            nonlocal pending_batch
            if not pending_batch:
                return []
            normalized_batch = await asyncio.gather(
                *(
                    asyncio.to_thread(
                        self.normalize_item,
                        source=source,
                        parsed_message=parsed,
                        root_path=root_path,
                    )
                    for parsed in pending_batch
                )
            )
            pending_batch = []
            return [item for item in normalized_batch if item is not None]

        for raw_index, raw_message in enumerate(raw_messages[cursor_offset:], start=cursor_offset):
            parsed = parse_message(message=raw_message, chat_id=chat_id, chat_title=chat_title)
            if include_types and parsed.message_type.value not in include_types:
                continue
            if exclude_types and parsed.message_type.value in exclude_types:
                continue
            external_key = self.build_external_key(parsed_message=parsed)
            if not self._should_include_by_sample(external_key=external_key, sample_percent=sync_run.sample_percent):
                continue
            pending_batch.append(parsed)
            pending_next_cursor = raw_index + 1
            if len(pending_batch) >= self._NORMALIZE_BATCH_SIZE:
                current_cursor = pending_next_cursor
                yield ScannedSyncBatch(
                    manifest_path=manifest_path,
                    items=await _flush_pending(),
                    next_cursor=str(current_cursor) if current_cursor is not None else None,
                )

        tail_batch = await _flush_pending()
        if tail_batch:
            current_cursor = pending_next_cursor
            yield ScannedSyncBatch(
                manifest_path=manifest_path,
                items=tail_batch,
                next_cursor=str(current_cursor) if current_cursor is not None else None,
            )
