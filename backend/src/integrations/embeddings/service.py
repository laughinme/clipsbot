from __future__ import annotations

import asyncio
import hashlib
import math
import subprocess
import tempfile
import re
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable

from google import genai
from google.genai import types

from core.config import Settings, get_settings
from database.relational_db import CorpusAsset, CorpusItem


class EmbeddingProvider:
    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError

    def build_document_text(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
    ) -> str:
        raise NotImplementedError

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    async def embed_message(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
        media_bytes: bytes | None = None,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> list[float]:
        raise NotImplementedError


class StubEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _normalize(self, vector: list[float]) -> list[float]:
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            vector[0] = 1.0
            return vector
        return [value / magnitude for value in vector]

    def _feature_hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.settings.EMBEDDING_VECTOR_SIZE
        tokens = re.findall(r"[\w#@:/.\-]+", text.lower(), flags=re.UNICODE)
        if not tokens:
            tokens = ["empty"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.settings.EMBEDDING_VECTOR_SIZE
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        return self._normalize(vector)

    def _prepare_query(self, query: str) -> str:
        return f"task: search result | query: {query.strip()}"

    def _prepare_document(self, item: CorpusItem, media_asset: CorpusAsset | None = None) -> str:
        title = item.container_name or "none"
        body_parts = [
            f"type: {item.content_type}",
            f"author: {item.author_name or 'unknown'}",
        ]
        if item.text_content:
            body_parts.append(f"text: {item.text_content}")
        if item.caption:
            body_parts.append(f"caption: {item.caption}")
        if media_asset and media_asset.original_filename:
            body_parts.append(f"filename: {media_asset.original_filename}")
        if media_asset and media_asset.source_relative_path:
            body_parts.append(f"path: {media_asset.source_relative_path}")
        return f"title: {title} | text: {' | '.join(body_parts)}".strip()

    def build_document_text(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
    ) -> str:
        return self._prepare_document(item, media_asset)

    async def embed_query(self, text: str) -> list[float]:
        return self._feature_hash_embed(self._prepare_query(text))

    async def embed_text(self, text: str) -> list[float]:
        return self._feature_hash_embed(text)

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return [self._feature_hash_embed(text) for text in documents]

    async def embed_message(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
        media_bytes: bytes | None = None,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> list[float]:
        return self._feature_hash_embed(self._prepare_document(item, media_asset))


class VertexEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.EMBEDDING_REQUEST_CONCURRENCY)
        self._client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            http_options=types.HttpOptions(api_version="v1"),
        )
        self._async_models = self._client.aio.models

    def _prepare_query(self, query: str) -> str:
        return f"task: search result | query: {query.strip()}"

    def _prepare_document(self, item: CorpusItem, media_asset: CorpusAsset | None = None) -> str:
        title = item.container_name or "none"
        body_parts = [
            f"type: {item.content_type}",
            f"author: {item.author_name or 'unknown'}",
        ]
        if item.text_content:
            body_parts.append(f"text: {item.text_content}")
        if item.caption:
            body_parts.append(f"caption: {item.caption}")
        if media_asset and media_asset.original_filename:
            body_parts.append(f"filename: {media_asset.original_filename}")
        return f"title: {title} | text: {' | '.join(body_parts)}".strip()

    async def _report_progress(
        self,
        callback: Callable[[str, str | None], Awaitable[None]] | None,
        stage: str,
        detail: str | None = None,
    ) -> None:
        if callback is not None:
            await callback(stage, detail)

    def build_document_text(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
    ) -> str:
        return self._prepare_document(item, media_asset)

    def _extract_vectors(self, response) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            raise RuntimeError("Vertex embedding response did not contain embeddings.")
        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = list(getattr(embedding, "values", []) or [])
            if len(values) != self.settings.EMBEDDING_VECTOR_SIZE:
                raise RuntimeError(
                    f"Unexpected embedding size {len(values)} from Vertex, expected {self.settings.EMBEDDING_VECTOR_SIZE}."
                )
            vectors.append([float(value) for value in values])
        return vectors

    async def _call_embed_content(self, *, contents) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.EMBEDDING_REQUEST_MAX_RETRIES + 1):
            try:
                async with self._semaphore:
                    response = await asyncio.wait_for(
                        self._async_models.embed_content(
                            model=self.settings.GEMINI_EMBEDDING_MODEL,
                            contents=contents,
                        ),
                        timeout=self.settings.EMBEDDING_REQUEST_TIMEOUT_SEC,
                    )
                return self._extract_vectors(response)
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.EMBEDDING_REQUEST_MAX_RETRIES:
                    break
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        assert last_error is not None
        raise last_error

    async def _embed_parts(self, parts: list[types.Part]) -> list[float]:
        content = types.Content(parts=parts)
        return (await self._call_embed_content(contents=content))[0]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        if not documents:
            return []
        tasks = [self.embed_text(document) for document in documents]
        return await asyncio.gather(*tasks)

    async def embed_text(self, text: str) -> list[float]:
        return await self._embed_parts([types.Part.from_text(text=text)])

    async def _convert_audio_for_embedding(self, payload: bytes) -> tuple[bytes, str]:
        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
            def _run() -> bytes:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        "pipe:0",
                        "-t",
                        "80",
                        "-vn",
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        temp_file.name,
                    ],
                    input=payload,
                    check=True,
                )
                return Path(temp_file.name).read_bytes()

            return await asyncio.wait_for(
                asyncio.to_thread(_run),
                timeout=self.settings.EMBEDDING_MEDIA_CONVERSION_TIMEOUT_SEC,
            ), "audio/wav"

    async def _convert_video_for_embedding(self, payload: bytes) -> tuple[bytes, str]:
        def _run_ffmpeg() -> bytes:
            process = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-t",
                    "120",
                    "-an",
                    "-vcodec",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "frag_keyframe+empty_moov",
                    "-f",
                    "mp4",
                    "pipe:1",
                ],
                input=payload,
                stdout=subprocess.PIPE,
                check=True,
            )
            return process.stdout

        return await asyncio.wait_for(
            asyncio.to_thread(_run_ffmpeg),
            timeout=self.settings.EMBEDDING_MEDIA_CONVERSION_TIMEOUT_SEC,
        ), "video/mp4"

    async def _prepare_media_part(self, item: CorpusItem, media_asset: CorpusAsset | None, media_bytes: bytes) -> types.Part:
        mime_type = (media_asset.mime_type or "").lower()
        if item.content_type in {"voice", "audio"}:
            media_bytes, mime_type = await self._convert_audio_for_embedding(media_bytes)
            return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)

        if item.content_type in {"video", "video_note"}:
            media_bytes, mime_type = await self._convert_video_for_embedding(media_bytes)
            return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)

        if item.content_type == "photo":
            if mime_type not in {"image/jpeg", "image/png"}:
                raise RuntimeError(f"Unsupported image mime type for embedding: {mime_type or 'unknown'}")
            return types.Part.from_bytes(data=media_bytes, mime_type=mime_type)

        raise RuntimeError(f"Unsupported media type for embedding: {item.content_type}")

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed_parts([types.Part.from_text(text=self._prepare_query(text))])

    async def embed_message(
        self,
        item: CorpusItem,
        media_asset: CorpusAsset | None = None,
        media_bytes: bytes | None = None,
        progress_callback: Callable[[str, str | None], Awaitable[None]] | None = None,
    ) -> list[float]:
        document_text = self._prepare_document(item, media_asset)
        parts = [types.Part.from_text(text=document_text)]
        if item.content_type != "text" and media_asset and media_bytes:
            asset_detail = media_asset.source_relative_path or media_asset.mime_type or item.content_type
            try:
                if item.content_type in {"voice", "audio"}:
                    await self._report_progress(progress_callback, "convert_audio", asset_detail)
                elif item.content_type in {"video", "video_note"}:
                    await self._report_progress(progress_callback, "convert_video", asset_detail)
                elif item.content_type == "photo":
                    await self._report_progress(progress_callback, "prepare_photo", asset_detail)
                parts.append(await self._prepare_media_part(item, media_asset, media_bytes))
                await self._report_progress(progress_callback, "vertex_request", asset_detail)
                return await self._embed_parts(parts)
            except Exception:
                await self._report_progress(progress_callback, "vertex_fallback_text", asset_detail)
                return await self._embed_parts([types.Part.from_text(text=document_text)])
        await self._report_progress(progress_callback, "vertex_request", item.content_type)
        return await self._embed_parts(parts)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "vertex":
        return VertexEmbeddingProvider(settings)
    return StubEmbeddingProvider(settings)


def clear_embedding_provider_cache() -> None:
    get_embedding_provider.cache_clear()
