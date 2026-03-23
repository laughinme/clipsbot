from __future__ import annotations

import asyncio
from io import BytesIO
import json
import logging
import subprocess

from aio_pika import IncomingMessage, connect_robust
from mutagen.mp3 import MP3

from broker import CLIPS_PROCESS_QUEUE, MAINTENANCE_QUEUE, ensure_topology
from core.config import configure_logging, get_settings
from database.relational_db import ClipsInterface, dispose_engine, get_session_factory, wait_for_db
from service.media import get_media_storage_service


logger = logging.getLogger(__name__)


async def _convert_audio_to_mp3(payload: bytes) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "128k",
        "-f",
        "mp3",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(payload)
    if process.returncode != 0:
        error_text = stderr.decode("utf-8", errors="replace").strip() or "ffmpeg conversion failed"
        raise RuntimeError(error_text)
    return stdout


async def _process_clip_uploaded(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    storage = get_media_storage_service()

    async with session_factory() as session:
        repo = ClipsInterface(session)
        clip = await repo.get_by_id(payload["clip_id"])
        if clip is None or not clip.object_key:
            logger.warning("Clip %s not found during worker processing", payload["clip_id"])
            await session.commit()
            return

        try:
            content = await asyncio.to_thread(
                lambda: storage.get_object_bytes(bucket=payload["bucket"], key=payload["object_key"])
            )
            converted = False
            try:
                audio = MP3(BytesIO(content))
                final_content = content
            except Exception:
                final_content = await _convert_audio_to_mp3(content)
                audio = MP3(BytesIO(final_content))
                converted = True

            if converted:
                await asyncio.to_thread(
                    lambda: storage.put_object_bytes(
                        bucket=payload["bucket"],
                        key=payload["object_key"],
                        payload=final_content,
                        content_type="audio/mpeg",
                    )
                )

            clip.bucket = payload["bucket"]
            clip.object_key = payload["object_key"]
            clip.size_bytes = len(final_content)
            clip.duration_ms = int(audio.info.length * 1000)
            clip.mime_type = "audio/mpeg"
            clip.status = "ready"
        except Exception as exc:
            logger.exception("Failed to process clip %s: %s", payload["clip_id"], exc)
            clip.status = "failed"

        await session.commit()


async def _process_maintenance_job(payload: dict[str, str]) -> None:
    task_name = payload.get("task")
    if task_name != "clips.cleanup_stale_uploads":
        logger.info("Skipping unknown maintenance task: %s", task_name)
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = ClipsInterface(session)
        updated = await repo.mark_stale_uploads_failed()
        await session.commit()
        logger.info("Marked %d stale uploads as failed", updated)


async def _handle_message(message: IncomingMessage) -> None:
    try:
        payload = json.loads(message.body.decode("utf-8"))
        if payload.get("task"):
            await _process_maintenance_job(payload)
        else:
            await _process_clip_uploaded(payload)
    except Exception:
        if message.redelivered:
            await message.reject(requeue=False)
        else:
            await message.nack(requeue=True)
        raise
    else:
        await message.ack()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    await wait_for_db()

    connection = await connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        await ensure_topology(channel)

        clip_queue = await channel.get_queue(CLIPS_PROCESS_QUEUE, ensure=False)
        maintenance_queue = await channel.get_queue(MAINTENANCE_QUEUE, ensure=False)

        await clip_queue.consume(_handle_message, no_ack=False)
        await maintenance_queue.consume(_handle_message, no_ack=False)

        logger.info("Worker started and consuming queues")
        await asyncio.Future()

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
