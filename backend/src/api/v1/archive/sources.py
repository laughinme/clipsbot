from typing import Annotated
from uuid import UUID

import asyncpg
import json
from fastapi import APIRouter, Depends, Query

from core.config import Settings, get_settings
from core.security import require
from database.relational_db import User
from domain.archive import (
    SourceConnectionModel,
    SourceCreateRequest,
    SourceListResponse,
    SourceUpdateRequest,
    SourceSyncCreateRequest,
    SyncRunListResponse,
    SyncRunModel,
    SyncRunStatusResponse,
)
from service.archive_corpus import ArchiveSourceService, get_archive_source_service

router = APIRouter()


@router.get(
    path="/sources",
    response_model=SourceListResponse,
    summary="List archive sources",
)
async def list_sources(
    settings: Annotated[Settings, Depends(get_settings)],
):
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    connection = await asyncpg.connect(dsn=dsn)
    try:
        rows = await connection.fetch(
            """
            select id, kind, slug, display_name, status, config_json, created_at, updated_at
            from source_connections
            order by created_at desc
            """
        )
    finally:
        await connection.close()

    return SourceListResponse(
        items=[
            SourceConnectionModel(
                id=row["id"],
                kind=row["kind"],
                slug=row["slug"],
                display_name=row["display_name"],
                status=row["status"],
                config_json=json.loads(row["config_json"]) if isinstance(row["config_json"], str) else (row["config_json"] or {}),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )


@router.post(
    path="/sources",
    response_model=SourceConnectionModel,
    summary="Create archive source",
)
async def create_source(
    payload: SourceCreateRequest,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveSourceService, Depends(get_archive_source_service)],
):
    return await svc.create_source(payload)


@router.patch(
    path="/sources/{source_id}",
    response_model=SourceConnectionModel,
    summary="Update archive source",
)
async def update_source(
    source_id: UUID,
    payload: SourceUpdateRequest,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveSourceService, Depends(get_archive_source_service)],
):
    return await svc.update_source(source_id, payload)


@router.post(
    path="/sources/{source_id}/syncs",
    response_model=SyncRunModel,
    summary="Start archive sync run",
)
async def create_sync_run(
    source_id: UUID,
    payload: SourceSyncCreateRequest,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveSourceService, Depends(get_archive_source_service)],
):
    return await svc.start_sync(source_id, payload)


@router.get(
    path="/sources/{source_id}/syncs",
    response_model=SyncRunListResponse,
    summary="List sync runs for a source",
)
async def list_sync_runs(
    source_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveSourceService, Depends(get_archive_source_service)],
    limit: int = Query(20, ge=1, le=100),
):
    return await svc.list_syncs(source_id, limit=limit)


@router.get(
    path="/syncs/{sync_run_id}",
    response_model=SyncRunStatusResponse,
    summary="Get archive sync run status",
)
async def get_sync_run_status(
    sync_run_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveSourceService, Depends(get_archive_source_service)],
):
    return await svc.get_sync_status(sync_run_id)
