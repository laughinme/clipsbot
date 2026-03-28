from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types

from core.config import Settings
from database.relational_db import CorpusAsset, CorpusItem
from integrations.gcs_staging import GcsStagingService


def _compact_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _join_text(parts: list[str | None]) -> str:
    return "\n".join(part for part in (_compact_text(value) for value in parts) if part)


@dataclass(slots=True)
class EnrichmentOutput:
    text: str | None
    language_code: str | None
    provider: str
    provider_model: str | None


class OcrProvider:
    async def extract(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        raise NotImplementedError


class TranscriptProvider:
    async def transcribe(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        raise NotImplementedError


class SummaryProvider:
    async def summarize(
        self,
        *,
        item: CorpusItem,
        ocr_text: str | None,
        transcript_text: str | None,
    ) -> EnrichmentOutput:
        raise NotImplementedError


class StubOcrProvider(OcrProvider):
    async def extract(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        del asset, payload
        text = _join_text([item.caption, item.text_content])
        return EnrichmentOutput(
            text=text or None,
            language_code=None,
            provider="stub",
            provider_model="stub-ocr",
        )


class StubTranscriptProvider(TranscriptProvider):
    async def transcribe(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        del asset, payload
        text = _join_text([item.text_content, item.caption])
        return EnrichmentOutput(
            text=text or None,
            language_code=None,
            provider="stub",
            provider_model="stub-transcript",
        )


class StubSummaryProvider(SummaryProvider):
    async def summarize(
        self,
        *,
        item: CorpusItem,
        ocr_text: str | None,
        transcript_text: str | None,
    ) -> EnrichmentOutput:
        raw = _join_text([item.text_content, item.caption, ocr_text, transcript_text])
        if not raw:
            return EnrichmentOutput(
                text=None,
                language_code=None,
                provider="stub",
                provider_model="stub-summary",
            )
        sentence_like = re.split(r"(?<=[.!?])\s+", raw)
        summary = " ".join(part.strip() for part in sentence_like[:2] if part.strip()) or raw[:280]
        return EnrichmentOutput(
            text=summary,
            language_code=None,
            provider="stub",
            provider_model="stub-summary",
        )


class VisionOcrProvider(OcrProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _call(self, payload: bytes) -> EnrichmentOutput:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=payload)
        response = client.document_text_detection(image=image)
        if response.error.message:
            raise RuntimeError(response.error.message)
        text = _compact_text(response.full_text_annotation.text if response.full_text_annotation else None)
        return EnrichmentOutput(
            text=text or None,
            language_code=None,
            provider="vision",
            provider_model="DOCUMENT_TEXT_DETECTION",
        )

    async def extract(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        del item, asset
        return await asyncio.wait_for(
            asyncio.to_thread(self._call, payload),
            timeout=self.settings.OCR_REQUEST_TIMEOUT_SEC,
        )


class SpeechV2TranscriptProvider(TranscriptProvider):
    def __init__(self, settings: Settings, gcs_staging: GcsStagingService) -> None:
        self.settings = settings
        self.gcs_staging = gcs_staging

    def _normalize_audio_payload(self, *, item: CorpusItem, payload: bytes) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_output:
            input_args = ["-i", "pipe:0"]
            if item.content_type == "video":
                input_args = ["-i", "pipe:0", "-vn"]

            process = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    *input_args,
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    temp_output.name,
                ],
                input=payload,
                check=True,
            )
            del process
            return Path(temp_output.name).read_bytes()

    def _extract_transcript_text(self, response, *, audio_uri: str) -> str:
        file_result = response.results[audio_uri]
        transcript = file_result.transcript
        parts: list[str] = []
        for result in transcript.results:
            if not result.alternatives:
                continue
            candidate = _compact_text(result.alternatives[0].transcript)
            if candidate:
                parts.append(candidate)
        return " ".join(parts).strip()

    def _call_batch_recognize(self, *, audio_uri: str, duration_ms: int | None) -> EnrichmentOutput:
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech

        client = SpeechClient()
        duration_seconds = (duration_ms or 0) / 1000
        model = self.settings.STT_SHORT_MODEL if duration_seconds and duration_seconds <= 60 else self.settings.STT_LONG_MODEL
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=self.settings.transcript_language_codes,
            model=model,
        )
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=f"projects/{self.settings.GOOGLE_CLOUD_PROJECT}/locations/global/recognizers/_",
            config=config,
            files=[cloud_speech.BatchRecognizeFileMetadata(uri=audio_uri)],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig(),
            ),
        )
        operation = client.batch_recognize(request=request)
        response = operation.result(timeout=self.settings.TRANSCRIPT_REQUEST_TIMEOUT_SEC)
        text = self._extract_transcript_text(response, audio_uri=audio_uri)
        return EnrichmentOutput(
            text=text or None,
            language_code=self.settings.transcript_language_codes[0] if self.settings.transcript_language_codes else None,
            provider="speech_v2",
            provider_model=model,
        )

    async def transcribe(self, *, item: CorpusItem, asset: CorpusAsset, payload: bytes) -> EnrichmentOutput:
        normalized = await asyncio.to_thread(self._normalize_audio_payload, item=item, payload=payload)
        filename = (Path(asset.original_filename or asset.object_key).stem or "audio") + ".wav"
        audio_uri = await self.gcs_staging.upload_bytes(
            scope="speech",
            item_key=item.stable_key,
            filename=filename,
            payload=normalized,
            content_type="audio/wav",
        )
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._call_batch_recognize,
                    audio_uri=audio_uri,
                    duration_ms=asset.duration_ms,
                ),
                timeout=self.settings.TRANSCRIPT_REQUEST_TIMEOUT_SEC + 30,
            )
        finally:
            try:
                await self.gcs_staging.delete_uri(audio_uri)
            except Exception:
                pass


class VertexSummaryProvider(SummaryProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(max(1, settings.EMBEDDING_REQUEST_CONCURRENCY))
        self._client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            http_options=types.HttpOptions(api_version="v1"),
        )
        self._models = self._client.aio.models

    def _prompt(self, *, item: CorpusItem, ocr_text: str | None, transcript_text: str | None) -> str:
        source_text = _join_text(
            [
                f"type: {item.content_type}",
                f"container: {item.container_name or item.container_external_id or 'unknown'}",
                f"author: {item.author_name or item.author_external_id or 'unknown'}",
                f"message_text: {item.text_content or ''}",
                f"caption: {item.caption or ''}",
                f"ocr_text: {ocr_text or ''}",
                f"transcript: {transcript_text or ''}",
            ]
        )
        return (
            "You summarize archive items for search quality.\n"
            "Write at most two short sentences in the same language as the source when possible.\n"
            "Use only the evidence provided below.\n"
            "Do not invent names, context, or missing details.\n\n"
            f"{source_text}"
        )

    async def summarize(
        self,
        *,
        item: CorpusItem,
        ocr_text: str | None,
        transcript_text: str | None,
    ) -> EnrichmentOutput:
        raw = _join_text([item.text_content, item.caption, ocr_text, transcript_text])
        if not raw:
            return EnrichmentOutput(
                text=None,
                language_code=None,
                provider="vertex",
                provider_model=self.settings.GEMINI_SUMMARY_MODEL,
            )
        async with self._semaphore:
            response = await asyncio.wait_for(
                self._models.generate_content(
                    model=self.settings.GEMINI_SUMMARY_MODEL,
                    contents=self._prompt(item=item, ocr_text=ocr_text, transcript_text=transcript_text),
                ),
                timeout=self.settings.SUMMARY_REQUEST_TIMEOUT_SEC,
            )
        return EnrichmentOutput(
            text=_compact_text(response.text),
            language_code=None,
            provider="vertex",
            provider_model=self.settings.GEMINI_SUMMARY_MODEL,
        )


class ArchiveEnrichmentProviders:
    def __init__(
        self,
        *,
        ocr: OcrProvider,
        transcript: TranscriptProvider,
        summary: SummaryProvider,
    ) -> None:
        self.ocr = ocr
        self.transcript = transcript
        self.summary = summary
