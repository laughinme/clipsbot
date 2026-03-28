from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from domain.archive import ArchiveContentType, ProjectionIndexStatus

FILE_NOT_INCLUDED_MARKER = "(File not included"

_MEDIA_TYPE_MAPPING: dict[str, ArchiveContentType] = {
    "voice_message": ArchiveContentType.VOICE,
    "video_message": ArchiveContentType.VIDEO_NOTE,
    "video_file": ArchiveContentType.VIDEO,
    "audio_file": ArchiveContentType.AUDIO,
    "document": ArchiveContentType.DOCUMENT,
    "sticker": ArchiveContentType.STICKER,
    "animation": ArchiveContentType.ANIMATION,
}


@dataclass(slots=True)
class ParsedTelegramMessage:
    telegram_message_id: int
    chat_id: int | None
    chat_title: str | None
    author_telegram_id: int | None
    author_name: str | None
    timestamp: datetime
    message_type: ArchiveContentType
    text_content: str | None
    caption: str | None
    reply_to_message_id: int | None
    has_media: bool
    source_relative_path: str | None
    original_filename: str | None
    mime_type: str | None
    file_size_bytes: int | None
    duration_ms: int | None
    width: int | None
    height: int | None
    index_status: ProjectionIndexStatus
    index_error: str | None


def flatten_telegram_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    parts.append(str(text))
        return "".join(parts).strip()
    return ""


def parse_author_telegram_id(raw_value: Any) -> int | None:
    if raw_value is None:
        return None
    match = re.search(r"(\d+)$", str(raw_value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def normalize_message_type(message: dict[str, Any]) -> ArchiveContentType:
    if message.get("type") == "service":
        return ArchiveContentType.SERVICE
    if "photo" in message:
        return ArchiveContentType.PHOTO
    media_type = message.get("media_type")
    if media_type in _MEDIA_TYPE_MAPPING:
        return _MEDIA_TYPE_MAPPING[media_type]
    if flatten_telegram_text(message.get("text")):
        return ArchiveContentType.TEXT
    return ArchiveContentType.UNKNOWN


def resolve_media_relative_path(message: dict[str, Any], message_type: ArchiveContentType) -> str | None:
    raw_path = message.get("photo") if message_type == ArchiveContentType.PHOTO else message.get("file")
    if not raw_path or not isinstance(raw_path, str):
        return None
    if raw_path.startswith(FILE_NOT_INCLUDED_MARKER):
        return None
    return raw_path


def to_timestamp(message: dict[str, Any]) -> datetime:
    unix_value = message.get("date_unixtime")
    if unix_value is not None:
        try:
            return datetime.fromtimestamp(int(unix_value), tz=UTC)
        except Exception:
            pass
    raw = str(message.get("date") or "")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def guess_mime_type(relative_path: str | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback
    if not relative_path:
        return None
    guessed, _ = mimetypes.guess_type(relative_path)
    return guessed


@lru_cache(maxsize=16384)
def _sha256_file_cached(path_str: str, size_bytes: int, mtime_ns: int) -> str:
    digest = hashlib.sha256()
    path = Path(path_str)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    stat = path.stat()
    return _sha256_file_cached(
        str(path.resolve()),
        stat.st_size,
        stat.st_mtime_ns,
    )


def parse_message(
    *,
    message: dict[str, Any],
    chat_id: int | None,
    chat_title: str | None,
) -> ParsedTelegramMessage:
    message_type = normalize_message_type(message)
    text_value = flatten_telegram_text(message.get("text"))
    text_content = text_value if message_type == ArchiveContentType.TEXT and text_value else None
    caption = text_value if message_type != ArchiveContentType.TEXT and text_value else None

    source_relative_path = resolve_media_relative_path(message, message_type)
    has_media = source_relative_path is not None or message_type in {
        ArchiveContentType.PHOTO,
        ArchiveContentType.VOICE,
        ArchiveContentType.VIDEO_NOTE,
        ArchiveContentType.VIDEO,
        ArchiveContentType.AUDIO,
        ArchiveContentType.DOCUMENT,
    }

    index_status = ProjectionIndexStatus.SKIPPED
    index_error: str | None = None
    if message_type in {
        ArchiveContentType.TEXT,
        ArchiveContentType.PHOTO,
        ArchiveContentType.VOICE,
        ArchiveContentType.VIDEO_NOTE,
        ArchiveContentType.VIDEO,
        ArchiveContentType.AUDIO,
    }:
        if message_type == ArchiveContentType.TEXT:
            if text_content:
                index_status = ProjectionIndexStatus.QUEUED
            else:
                index_error = "empty_text_message"
        elif source_relative_path:
            index_status = ProjectionIndexStatus.QUEUED
        else:
            index_error = "media_missing_from_export"
    elif message_type in {
        ArchiveContentType.SERVICE,
        ArchiveContentType.STICKER,
        ArchiveContentType.ANIMATION,
        ArchiveContentType.DOCUMENT,
    }:
        index_error = f"unsupported_content_type:{message_type.value}"
    else:
        index_error = "unsupported_message_shape"

    raw_file_name = message.get("file_name")
    original_filename = None
    if isinstance(raw_file_name, str) and raw_file_name.strip():
        original_filename = Path(raw_file_name).name
    elif source_relative_path:
        original_filename = Path(source_relative_path).name

    return ParsedTelegramMessage(
        telegram_message_id=int(message["id"]),
        chat_id=chat_id,
        chat_title=chat_title,
        author_telegram_id=parse_author_telegram_id(message.get("from_id")),
        author_name=message.get("from"),
        timestamp=to_timestamp(message),
        message_type=message_type,
        text_content=text_content,
        caption=caption,
        reply_to_message_id=message.get("reply_to_message_id"),
        has_media=has_media,
        source_relative_path=source_relative_path,
        original_filename=original_filename,
        mime_type=guess_mime_type(source_relative_path, message.get("mime_type")),
        file_size_bytes=message.get("file_size") or message.get("photo_file_size"),
        duration_ms=int(message["duration_seconds"] * 1000) if message.get("duration_seconds") else None,
        width=message.get("width"),
        height=message.get("height"),
        index_status=index_status,
        index_error=index_error,
    )
