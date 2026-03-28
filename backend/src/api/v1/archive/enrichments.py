from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.errors import BadRequestError
from core.security import require
from database.relational_db import User
from domain.archive import (
    EnrichmentRunCreateRequest,
    EnrichmentRunListResponse,
    EnrichmentRunModel,
    EnrichmentRunStatusResponse,
)
from service.archive_enrichments import ArchiveEnrichmentService, get_archive_enrichment_service

router = APIRouter()


@router.post(
    path="/enrichment-runs",
    response_model=EnrichmentRunModel,
    summary="Start an archive enrichment backfill run",
)
async def create_enrichment_run(
    payload: EnrichmentRunCreateRequest,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveEnrichmentService, Depends(get_archive_enrichment_service)],
):
    run = await svc.start_manual_enrichment_run(payload)
    if run is None:
        raise BadRequestError("No corpus items matched the requested enrichment scope.")
    return run


@router.get(
    path="/enrichment-runs/{enrichment_run_id}",
    response_model=EnrichmentRunStatusResponse,
    summary="Get archive enrichment run status",
)
async def get_enrichment_run(
    enrichment_run_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveEnrichmentService, Depends(get_archive_enrichment_service)],
):
    return await svc.get_enrichment_run(enrichment_run_id)


@router.get(
    path="/sources/{source_id}/enrichment-runs",
    response_model=EnrichmentRunListResponse,
    summary="List enrichment runs for a source",
)
async def list_source_enrichment_runs(
    source_id: UUID,
    _: Annotated[User, Depends(require("admin"))],
    svc: Annotated[ArchiveEnrichmentService, Depends(get_archive_enrichment_service)],
    limit: int = Query(20, ge=1, le=100),
):
    return await svc.list_enrichment_runs(source_id, limit=limit)
