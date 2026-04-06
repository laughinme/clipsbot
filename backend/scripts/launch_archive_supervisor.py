from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_SYNC_RUN_ID = "3128fa65-3c4e-4976-a476-3263a306f054"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("APP_STAGE", "dev")
    env.setdefault("DEBUG", "true")
    env.setdefault("PYTHONPATH", "src")
    env.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:secret@localhost:5439/templatepg_test")
    env.setdefault("REDIS_URL", "redis://localhost:6380/9")
    env.setdefault("STORAGE_ENDPOINT_INTERNAL", "http://localhost:9002")
    env.setdefault("STORAGE_ENDPOINT_PUBLIC", "http://localhost:9002")
    env.setdefault("STORAGE_REGION", "us-east-1")
    env.setdefault("STORAGE_ACCESS_KEY", "minioadmin")
    env.setdefault("STORAGE_SECRET_KEY", "minioadmin")
    env.setdefault("STORAGE_PUBLIC_BUCKET", "media-public")
    env.setdefault("STORAGE_PRIVATE_BUCKET", "media-private")
    env.setdefault("STORAGE_ARCHIVE_BUCKET", "media-private")
    env.setdefault("STORAGE_USE_PATH_STYLE", "true")
    env.setdefault("STORAGE_AUTO_CREATE_BUCKETS", "false")
    env.setdefault("RABBITMQ_ENABLED", "false")
    env.setdefault("QDRANT_ENABLED", "true")
    env.setdefault("QDRANT_URL", "http://localhost:6333")
    env.setdefault("QDRANT_LOCAL_PATH", "")
    env.setdefault("QDRANT_COLLECTION", "knowledge_corpus_restored_http")
    env.setdefault("EMBEDDING_PROVIDER", "vertex")
    env.setdefault("EMBEDDING_REQUEST_CONCURRENCY", "16")
    env.setdefault("TEXT_EMBED_BATCH_SIZE", "128")
    env.setdefault("GOOGLE_CLOUD_PROJECT", "project-e5159f37-a786-495c-a11")
    env.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    env.setdefault("OCR_PROVIDER", "stub")
    env.setdefault("TRANSCRIPT_PROVIDER", "stub")
    env.setdefault("SUMMARY_PROVIDER", "stub")
    env.setdefault("ARCHIVE_AUTO_ENRICH_ON_SYNC", "false")
    env.setdefault("ARCHIVE_IMPORT_ALLOWED_ROOTS", "/Users/laughinme/Downloads/chats")
    return env


def main() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    sync_run_id = os.environ.get("ARCHIVE_SYNC_RUN_ID", DEFAULT_SYNC_RUN_ID)
    pid_file = Path(os.environ.get("ARCHIVE_SUPERVISOR_PID_FILE", "/tmp/archive-supervisor.pid"))
    log_file = Path(os.environ.get("ARCHIVE_SUPERVISOR_LOG_FILE", "/tmp/archive-supervisor.log"))
    use_caffeinate = os.environ.get("ARCHIVE_USE_CAFFEINATE", "1") == "1"

    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text().strip())
            os.kill(existing_pid, 0)
        except Exception:
            pid_file.unlink(missing_ok=True)
        else:
            print(f"archive supervisor already running: pid={existing_pid}")
            return 0

    cmd = [
        "poetry",
        "run",
        "python",
        "scripts/archive_supervisor.py",
        "--sync-run-id",
        sync_run_id,
        "--poll",
        os.environ.get("ARCHIVE_SUPERVISOR_POLL", "1"),
        "--stale-seconds",
        os.environ.get("ARCHIVE_SUPERVISOR_STALE_SECONDS", "30"),
        "--refresh-every",
        os.environ.get("ARCHIVE_SUPERVISOR_REFRESH_EVERY", "50"),
        "--concurrency",
        os.environ.get("ARCHIVE_SUPERVISOR_CONCURRENCY", "12"),
        "--media-concurrency",
        os.environ.get("ARCHIVE_SUPERVISOR_MEDIA_CONCURRENCY", "2"),
        "--photo-concurrency",
        os.environ.get("ARCHIVE_SUPERVISOR_PHOTO_CONCURRENCY", "6"),
        "--audio-concurrency",
        os.environ.get("ARCHIVE_SUPERVISOR_AUDIO_CONCURRENCY", "6"),
        "--video-concurrency",
        os.environ.get("ARCHIVE_SUPERVISOR_VIDEO_CONCURRENCY", "3"),
        "--gc-every",
        os.environ.get("ARCHIVE_SUPERVISOR_GC_EVERY", "10"),
        "--text-first",
        os.environ.get("ARCHIVE_SUPERVISOR_TEXT_FIRST", "1"),
        "--prioritize-types",
        os.environ.get("ARCHIVE_SUPERVISOR_PRIORITIZE_TYPES", "0"),
        "--balance-media",
        os.environ.get("ARCHIVE_SUPERVISOR_BALANCE_MEDIA", "0"),
        "--state-file",
        os.environ.get("ARCHIVE_SUPERVISOR_STATE_FILE", "/tmp/archive-supervisor-state.json"),
    ]
    if use_caffeinate:
        cmd = ["caffeinate", "-dimsu", *cmd]

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as log_fp:
        proc = subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=_env(),
            stdin=subprocess.DEVNULL,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid_file.write_text(f"{proc.pid}\n")

    time.sleep(1)
    try:
        os.kill(proc.pid, 0)
    except OSError:
        print("archive supervisor failed to start")
        try:
            print(log_file.read_text())
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)
        return 1

    print(f"archive supervisor started: pid={proc.pid}")
    print(f"log file: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
