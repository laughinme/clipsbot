from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from database.relational_db import get_session_factory


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live dashboard for local archive sync/index progress.")
    parser.add_argument("--sync-run-id", type=str, default=None, help="Specific sync run id to monitor.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument(
        "--stale-seconds",
        type=float,
        default=30.0,
        help="Mark scanning as STALLED when heartbeat is older than this many seconds.",
    )
    parser.add_argument(
        "--active-limit",
        type=int,
        default=12,
        help="How many currently processing jobs to show.",
    )
    parser.add_argument(
        "--state-file",
        default="/tmp/archive-supervisor-state.json",
        help="Path to the JSON state file written by archive_supervisor.",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear the terminal between refreshes.",
    )
    return parser.parse_args()


async def _latest_sync_run_id() -> UUID | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.execute(text("select id from sync_runs order by created_at desc limit 1"))
        value = row.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None


async def _fetch_snapshot(sync_run_id: UUID, *, active_limit: int) -> dict[str, object] | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        sync_row = (
            await session.execute(
                text(
                    """
                    select
                        id,
                        status,
                        coverage_kind,
                        total_items,
                        new_items,
                        updated_items,
                        unchanged_items,
                        skipped_items,
                        indexed_items,
                        failed_items,
                        cursor,
                        scan_heartbeat_at,
                        updated_at
                    from sync_runs
                    where id = :sync_run_id
                    """
                ),
                {"sync_run_id": str(sync_run_id)},
            )
        ).mappings().first()
        if sync_row is None:
            return None

        jobs_row = (
            await session.execute(
                text(
                    """
                    select
                        coalesce(sum(case when status = 'queued' then 1 else 0 end), 0) as queued,
                        coalesce(sum(case when status = 'processing' then 1 else 0 end), 0) as processing,
                        coalesce(sum(case when status = 'done' then 1 else 0 end), 0) as done,
                        coalesce(sum(case when status = 'failed' then 1 else 0 end), 0) as failed
                    from indexing_jobs
                    where sync_run_id = :sync_run_id
                    """
                ),
                {"sync_run_id": str(sync_run_id)},
            )
        ).mappings().one()

        type_rows = (
            await session.execute(
                text(
                    """
                    select
                        ci.content_type,
                        coalesce(sum(case when ij.status = 'queued' then 1 else 0 end), 0) as queued,
                        coalesce(sum(case when ij.status = 'processing' then 1 else 0 end), 0) as processing,
                        coalesce(sum(case when ij.status = 'done' then 1 else 0 end), 0) as done,
                        coalesce(sum(case when ij.status = 'failed' then 1 else 0 end), 0) as failed
                    from indexing_jobs ij
                    join corpus_projections cp on cp.id = ij.projection_id
                    join corpus_items ci on ci.id = cp.corpus_item_id
                    where ij.sync_run_id = :sync_run_id
                    group by ci.content_type
                    order by
                        case ci.content_type
                            when 'text' then 0
                            when 'photo' then 1
                            when 'voice' then 2
                            when 'audio' then 3
                            when 'video_note' then 4
                            when 'video' then 5
                            else 6
                        end,
                        ci.content_type asc
                    """
                ),
                {"sync_run_id": str(sync_run_id)},
            )
        ).mappings().all()

        active_rows = (
            await session.execute(
                text(
                    """
                    select
                        ij.id,
                        ij.started_at,
                        ci.content_type,
                        ci.stable_key,
                        cp.projection_kind,
                        ca.source_relative_path
                    from indexing_jobs ij
                    join corpus_projections cp on cp.id = ij.projection_id
                    join corpus_items ci on ci.id = cp.corpus_item_id
                    left join corpus_assets ca
                        on ca.corpus_item_id = ci.id
                       and ca.role = 'primary'
                    where ij.sync_run_id = :sync_run_id
                      and ij.status = 'processing'
                    order by ij.started_at asc nulls last
                    limit :active_limit
                    """
                ),
                {"sync_run_id": str(sync_run_id), "active_limit": active_limit},
            )
        ).mappings().all()

        return {
            "sync": dict(sync_row),
            "jobs": dict(jobs_row),
            "types": [dict(row) for row in type_rows],
            "active": [dict(row) for row in active_rows],
        }


def _safe_int(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(str(value))
    except Exception:
        return 0


def _format_percent(done: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(done / total) * 100:.1f}%"


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    minutes, sec = divmod(max(seconds, 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


def _load_runtime_state(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"jobs": {}}


def _short_id(value: object) -> str:
    raw = str(value)
    return raw[:8]


def _trim(value: str | None, limit: int) -> str:
    if not value:
        return "-"
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _rate_per_min(history: deque[tuple[datetime, int]], window_seconds: int) -> float:
    if len(history) < 2:
        return 0.0
    newest_time, newest_value = history[-1]
    candidates = [entry for entry in history if (newest_time - entry[0]).total_seconds() <= window_seconds]
    if len(candidates) < 2:
        return 0.0
    oldest_time, oldest_value = candidates[0]
    seconds = max((newest_time - oldest_time).total_seconds(), 1e-6)
    return max((newest_value - oldest_value) * 60.0 / seconds, 0.0)


def _rate_since_start(history: deque[tuple[datetime, int]]) -> float:
    if len(history) < 2:
        return 0.0
    oldest_time, oldest_value = history[0]
    newest_time, newest_value = history[-1]
    seconds = max((newest_time - oldest_time).total_seconds(), 1e-6)
    return max((newest_value - oldest_value) * 60.0 / seconds, 0.0)


def _render(
    *,
    sync_run_id: UUID,
    snapshot: dict[str, object],
    runtime_state: dict[str, object],
    health: str,
    done_delta: int,
    cursor_delta: int,
    rate_per_min_1m: float,
    rate_per_min_5m: float,
    rate_per_min_total: float,
) -> str:
    sync = snapshot["sync"]
    jobs = snapshot["jobs"]
    type_rows = snapshot["types"]
    active_rows = snapshot["active"]
    assert isinstance(sync, dict)
    assert isinstance(jobs, dict)
    assert isinstance(type_rows, list)
    assert isinstance(active_rows, list)

    cursor = _safe_int(sync.get("cursor"))
    total_items = _safe_int(sync.get("total_items"))
    skipped = _safe_int(sync.get("skipped_items"))
    done = _safe_int(jobs.get("done"))
    queued = _safe_int(jobs.get("queued"))
    processing = _safe_int(jobs.get("processing"))
    failed = _safe_int(jobs.get("failed"))
    total_jobs = done + queued + processing + failed
    indexed_target = max(total_jobs, 0)
    remaining = queued + processing
    eta_rate = (
        rate_per_min_5m
        if rate_per_min_5m > 0.01
        else rate_per_min_1m
        if rate_per_min_1m > 0.01
        else rate_per_min_total
    )
    eta_seconds: int | None = None
    if eta_rate > 0.01 and remaining > 0:
        eta_seconds = int((remaining / eta_rate) * 60)
    runtime_jobs = runtime_state.get("jobs", {})
    if not isinstance(runtime_jobs, dict):
        runtime_jobs = {}

    lines: list[str] = []
    lines.append(f"Archive Monitor  sync_run={sync_run_id}")
    lines.append(
        f"status={sync.get('status')}  health={health}  coverage={sync.get('coverage_kind')}  "
        f"scan_total={total_items}  skipped={skipped}"
    )
    if cursor:
        lines.append(f"cursor={cursor}  delta_cursor={cursor_delta:+d}")
    lines.append(
        f"jobs_done={done} ({_format_percent(done, indexed_target)})  "
        f"processing={processing}  queued={queued}  failed={failed}  "
        f"delta_done={done_delta:+d}  rate_1m={rate_per_min_1m:.1f}/min  "
        f"rate_5m={rate_per_min_5m:.1f}/min  rate_all={rate_per_min_total:.1f}/min  "
        f"eta={_format_duration(eta_seconds)}"
    )

    active_stage_counts: dict[str, int] = {}
    for job_state in runtime_jobs.values():
        if not isinstance(job_state, dict):
            continue
        stage_name = str(job_state.get("stage") or "-")
        active_stage_counts[stage_name] = active_stage_counts.get(stage_name, 0) + 1
    if active_stage_counts:
        stage_mix = ", ".join(
            f"{stage}={count}"
            for stage, count in sorted(active_stage_counts.items(), key=lambda item: (-item[1], item[0]))
        )
        lines.append(f"active_stages={stage_mix}")
    lines.append("")
    lines.append("By Type")
    lines.append("type         done/total        done%    proc  queue  fail")
    for row in type_rows:
        if not isinstance(row, dict):
            continue
        content_type = str(row.get("content_type") or "-")
        row_done = _safe_int(row.get("done"))
        row_processing = _safe_int(row.get("processing"))
        row_queued = _safe_int(row.get("queued"))
        row_failed = _safe_int(row.get("failed"))
        row_total = row_done + row_processing + row_queued + row_failed
        lines.append(
            f"{content_type:<12} {row_done:>5}/{row_total:<11} {_format_percent(row_done, row_total):>7}  "
            f"{row_processing:>4}  {row_queued:>5}  {row_failed:>4}"
        )

    lines.append("")
    shown_active = len(active_rows)
    hidden_active = max(processing - shown_active, 0)
    lines.append(f"Active Jobs  showing={shown_active}  hidden={hidden_active}")
    if not active_rows:
        lines.append("  no processing jobs right now")
    else:
        lines.append("id       type        age      stage            stage_for  detail               stable_key                     asset")
        now = datetime.now(UTC)
        for row in active_rows:
            if not isinstance(row, dict):
                continue
            started_at = row.get("started_at")
            age_seconds: int | None = None
            if isinstance(started_at, datetime):
                age_seconds = int((now - started_at).total_seconds())
            state = runtime_jobs.get(str(row.get("id")), {})
            if not isinstance(state, dict):
                state = {}
            stage = str(state.get("stage") or "db_processing_only")
            stage_started_at = state.get("stage_started_at")
            stage_age_seconds: int | None = None
            if isinstance(stage_started_at, str):
                try:
                    stage_dt = datetime.fromisoformat(stage_started_at)
                    if stage_dt.tzinfo is None:
                        stage_dt = stage_dt.replace(tzinfo=UTC)
                    stage_age_seconds = int((now - stage_dt).total_seconds())
                except Exception:
                    stage_age_seconds = None
            detail = str(state.get("detail") or "-")
            lines.append(
                f"{_short_id(row.get('id')):<8} "
                f"{str(row.get('content_type') or '-'): <11} "
                f"{_format_duration(age_seconds): <8} "
                f"{_trim(stage, 15): <15} "
                f"{_format_duration(stage_age_seconds): <10} "
                f"{_trim(detail, 19): <19} "
                f"{_trim(str(row.get('stable_key') or '-'), 30): <30} "
                f"{_trim(str(row.get('source_relative_path') or '-'), 42)}"
            )

    lines.append("")
    lines.append("Legend")
    lines.append("  processing = jobs currently claimed and running")
    lines.append("  stage      = current local pipeline phase for the job")
    lines.append("  detail     = extra context for the current stage")
    lines.append("  delta_done = how many jobs finished since previous refresh")
    lines.append("  rate_1m    = short-window completed jobs per minute")
    lines.append("  rate_5m    = longer-window completed jobs per minute")
    lines.append("  rate_all   = completed jobs per minute since this monitor session started")
    lines.append("  eta        = rough remaining time using 5m rate, fallback to 1m, then rate_all")
    return "\n".join(lines)


async def main() -> None:
    args = _parse_args()
    sync_run_id = UUID(args.sync_run_id) if args.sync_run_id else await _latest_sync_run_id()
    if sync_run_id is None:
        print("No sync runs found.")
        return

    previous_done: int | None = None
    previous_cursor: int | None = None
    stagnant_ticks = 0
    history: deque[tuple[datetime, int]] = deque(maxlen=1200)

    while True:
        snapshot = await _fetch_snapshot(sync_run_id, active_limit=args.active_limit)
        if snapshot is None:
            print("sync run disappeared")
            return

        sync = snapshot["sync"]
        jobs = snapshot["jobs"]
        assert isinstance(sync, dict)
        assert isinstance(jobs, dict)

        cursor = _safe_int(sync.get("cursor"))
        done = _safe_int(jobs.get("done"))
        if previous_done is None:
            previous_done = done
        if previous_cursor is None:
            previous_cursor = cursor
        done_delta = done - previous_done
        cursor_delta = cursor - previous_cursor
        if done_delta == 0 and cursor_delta == 0:
            stagnant_ticks += 1
        else:
            stagnant_ticks = 0
        previous_done = done
        previous_cursor = cursor

        heartbeat = sync.get("scan_heartbeat_at")
        heartbeat_age_sec: int | None = None
        if isinstance(heartbeat, datetime):
            heartbeat_age_sec = int((datetime.now(UTC) - heartbeat).total_seconds())

        health = "LIVE"
        if str(sync.get("status")) == "scanning" and heartbeat_age_sec is not None and heartbeat_age_sec > int(args.stale_seconds):
            health = "STALLED"
        elif _safe_int(jobs.get("processing")) > 0:
            health = "LIVE"
        elif stagnant_ticks >= max(int(10 / max(args.interval, 0.1)), 3):
            health = "IDLE"

        now = datetime.now(UTC)
        history.append((now, done))
        while history and (now - history[0][0]).total_seconds() > 300:
            history.popleft()
        rate_per_min_1m = _rate_per_min(history, 60)
        rate_per_min_5m = _rate_per_min(history, 300)
        rate_per_min_total = _rate_since_start(history)
        runtime_state = _load_runtime_state(Path(args.state_file))

        if not args.no_clear and os.isatty(1):
            print("\x1b[2J\x1b[H", end="")

        print(
            _render(
                sync_run_id=sync_run_id,
                snapshot=snapshot,
                runtime_state=runtime_state,
                health=health,
                done_delta=done_delta,
                cursor_delta=cursor_delta,
                rate_per_min_1m=rate_per_min_1m,
                rate_per_min_5m=rate_per_min_5m,
                rate_per_min_total=rate_per_min_total,
            ),
            flush=True,
        )
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
