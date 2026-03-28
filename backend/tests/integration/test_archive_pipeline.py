import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from core.config import clear_settings_cache, get_settings
from database.relational_db import (
    CorpusAssetInterface,
    CorpusItem,
    CorpusItemInterface,
    CorpusProjectionInterface,
    EnrichmentJob,
    EnrichmentJobInterface,
    EnrichmentRunInterface,
    IndexingJob,
    IndexingJobInterface,
    SourceConnectionInterface,
    CorpusEnrichmentInterface,
    SyncRunInterface,
    UoW,
    get_session_factory,
)
from domain.archive import (
    ArchiveSearchRequest,
    EnrichmentRunCreateRequest,
    SourceCreateRequest,
    SourceSyncCreateRequest,
    SyncCoverageKind,
)
from integrations.embeddings import get_embedding_provider
from integrations.gcs_staging import get_gcs_staging_service
from integrations.qdrant import get_qdrant_service
from service.archive_corpus import ArchiveSourceService, get_source_adapter_registry
from service.archive_enrichments import ArchiveEnrichmentService, get_archive_enrichment_providers
from service.media import get_media_storage_service
from service.semantic_search.search_service import SemanticSearchService
from broker import BrokerPublisher


pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_integration_state"),
]


def _build_export(root, message_text: str, *, include_first_voice: bool = True) -> None:
    voice_dir = root / "voice_messages"
    voice_dir.mkdir(parents=True, exist_ok=True)
    if include_first_voice:
        (voice_dir / "audio_1.ogg").write_bytes(b"fake-voice-bytes")

    manifest = {
        "name": "Test Archive",
        "type": "personal_chat",
        "id": 777,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2026-03-20T10:00:00",
                "date_unixtime": "1773991200",
                "from": "Alice",
                "from_id": "user100",
                "text": message_text,
                "text_entities": [{"type": "plain", "text": message_text}],
            },
            {
                "id": 2,
                "type": "message",
                "date": "2026-03-20T10:05:00",
                "date_unixtime": "1773991500",
                "from": "Bob",
                "from_id": "user200",
                "media_type": "voice_message",
                "mime_type": "audio/ogg",
                "file": "voice_messages/audio_1.ogg" if include_first_voice else "(File not included. Change data exporting settings to download.)",
                "duration_seconds": 4,
                "text": "мем голосом",
                "text_entities": [{"type": "plain", "text": "мем голосом"}],
            },
            {
                "id": 3,
                "type": "service",
                "date": "2026-03-20T10:06:00",
                "date_unixtime": "1773991560",
                "from": "System",
                "from_id": "user300",
                "text": "",
                "text_entities": [],
            },
        ],
    }
    (root / "result.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def _build_archive_source_service(session) -> ArchiveSourceService:
    settings = get_settings()
    return ArchiveSourceService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        sync_run_repo=SyncRunInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_asset_repo=CorpusAssetInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        media_storage=get_media_storage_service(),
        broker=BrokerPublisher(settings),
        settings=settings,
        adapter_registry=get_source_adapter_registry(),
    )


def _build_enrichment_service(session) -> ArchiveEnrichmentService:
    settings = get_settings()
    return ArchiveEnrichmentService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        corpus_enrichment_repo=CorpusEnrichmentInterface(session),
        enrichment_run_repo=EnrichmentRunInterface(session),
        enrichment_job_repo=EnrichmentJobInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        media_storage=get_media_storage_service(),
        broker=BrokerPublisher(settings),
        providers=get_archive_enrichment_providers(
            settings=settings,
            gcs_staging=get_gcs_staging_service(),
        ),
        settings=settings,
    )


def _build_search_service(session) -> SemanticSearchService:
    settings = get_settings()
    return SemanticSearchService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        embeddings=get_embedding_provider(),
        qdrant=get_qdrant_service(),
        media_storage=get_media_storage_service(),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_archive_source_sync_and_search_pipeline(monkeypatch, tmp_path):
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant-db"))
    monkeypatch.setenv("QDRANT_COLLECTION", f"knowledge_corpus_{uuid4().hex}")
    monkeypatch.setenv("ARCHIVE_IMPORT_HOST_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_CONTAINER_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_ALLOWED_ROOTS", str(tmp_path))
    clear_settings_cache()

    export_root = tmp_path / "ChatExport_test"
    export_root.mkdir(parents=True, exist_ok=True)
    _build_export(export_root, "котик смеется в чате")

    session_factory = get_session_factory()

    async with session_factory() as session:
        source_service = _build_archive_source_service(session)
        source = await source_service.create_source(
            SourceCreateRequest(
                kind="telegram_desktop_export",
                slug="tg-main",
                display_name="Telegram Main",
                config_json={"export_path": str(export_root)},
            )
        )
        sync_run = await source_service.start_sync(
            source.id,
            SourceSyncCreateRequest(coverage_kind=SyncCoverageKind.FULL_SNAPSHOT),
        )
        await source_service.process_sync_run(sync_run.id)

        jobs = list(await session.scalars(select(IndexingJob)))
        search_service = _build_search_service(session)
        for job in jobs:
            await search_service.process_indexing_job(job.id)

        status = await source_service.refresh_sync_status(sync_run.id)
        assert status.total_items == 3
        assert status.indexed_items == 2
        assert status.skipped_items == 1

        response = await search_service.search(
            ArchiveSearchRequest(
                query="котик",
                limit=10,
            )
        )
        assert response.items
        assert any(item.text_preview and "котик" in item.text_preview for item in response.items)


@pytest.mark.asyncio
async def test_full_snapshot_rerun_updates_items_without_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant-db"))
    monkeypatch.setenv("QDRANT_COLLECTION", f"knowledge_corpus_{uuid4().hex}")
    monkeypatch.setenv("ARCHIVE_IMPORT_HOST_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_CONTAINER_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_ALLOWED_ROOTS", str(tmp_path))
    clear_settings_cache()

    export_root = tmp_path / "ChatExport_test"
    export_root.mkdir(parents=True, exist_ok=True)
    _build_export(export_root, "котик смеется в чате")

    session_factory = get_session_factory()

    async with session_factory() as session:
        source_service = _build_archive_source_service(session)
        search_service = _build_search_service(session)

        source = await source_service.create_source(
            SourceCreateRequest(
                kind="telegram_desktop_export",
                slug="tg-main",
                display_name="Telegram Main",
                config_json={"export_path": str(export_root)},
            )
        )

        first_sync = await source_service.start_sync(
            source.id,
            SourceSyncCreateRequest(coverage_kind=SyncCoverageKind.FULL_SNAPSHOT),
        )
        await source_service.process_sync_run(first_sync.id)
        for job in list(await session.scalars(select(IndexingJob))):
            await search_service.process_indexing_job(job.id)

        _build_export(export_root, "котик больше не смеется", include_first_voice=False)

        second_sync = await source_service.start_sync(
            source.id,
            SourceSyncCreateRequest(coverage_kind=SyncCoverageKind.FULL_SNAPSHOT),
        )
        await source_service.process_sync_run(second_sync.id)

        pending_jobs = list(
            await session.scalars(
                select(IndexingJob).where(IndexingJob.sync_run_id == second_sync.id)
            )
        )
        for job in pending_jobs:
            await search_service.process_indexing_job(job.id)

        item_count = await session.scalar(select(func.count(CorpusItem.id)))
        assert int(item_count or 0) == 3

        updated_text = await session.scalar(
            select(CorpusItem).where(CorpusItem.external_key == "777:1")
        )
        assert updated_text is not None
        assert updated_text.text_content == "котик больше не смеется"

        voice_item = await session.scalar(
            select(CorpusItem).where(CorpusItem.external_key == "777:2")
        )
        assert voice_item is not None
        assert voice_item.present_in_latest_sync is True

        service_item = await session.scalar(
            select(CorpusItem).where(CorpusItem.external_key == "777:3")
        )
        assert service_item is not None
        assert service_item.present_in_latest_sync is True

        response = await search_service.search(ArchiveSearchRequest(query="больше не смеется", limit=10))
        ids = [item.corpus_item_id for item in response.items]
        assert len(ids) == len(set(ids))
        assert updated_text.id in ids


@pytest.mark.asyncio
async def test_manual_enrichment_builds_derived_text_and_fused_search(monkeypatch, tmp_path):
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "qdrant-db"))
    monkeypatch.setenv("QDRANT_COLLECTION", f"knowledge_corpus_{uuid4().hex}")
    monkeypatch.setenv("ARCHIVE_IMPORT_HOST_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_CONTAINER_ROOT", "")
    monkeypatch.setenv("ARCHIVE_IMPORT_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("OCR_PROVIDER", "stub")
    monkeypatch.setenv("TRANSCRIPT_PROVIDER", "stub")
    monkeypatch.setenv("SUMMARY_PROVIDER", "stub")
    clear_settings_cache()

    export_root = tmp_path / "ChatExport_test"
    export_root.mkdir(parents=True, exist_ok=True)
    _build_export(export_root, "где тот мем про лицей")

    session_factory = get_session_factory()
    async with session_factory() as session:
        source_service = _build_archive_source_service(session)
        search_service = _build_search_service(session)
        enrichment_service = _build_enrichment_service(session)

        source = await source_service.create_source(
            SourceCreateRequest(
                kind="telegram_desktop_export",
                slug="tg-main",
                display_name="Telegram Main",
                config_json={"export_path": str(export_root)},
            )
        )
        sync_run = await source_service.start_sync(
            source.id,
            SourceSyncCreateRequest(coverage_kind=SyncCoverageKind.FULL_SNAPSHOT),
        )
        await source_service.process_sync_run(sync_run.id)

        for job in list(await session.scalars(select(IndexingJob))):
            await search_service.process_indexing_job(job.id)

        enrichment_run = await enrichment_service.start_manual_enrichment_run(
            EnrichmentRunCreateRequest(
                source_ids=[source.id],
                content_types=["text", "voice"],
                present_in_latest_sync=True,
                sample_percent=100,
            )
        )
        assert enrichment_run is not None

        for job in list(await session.scalars(select(EnrichmentJob))):
            await enrichment_service.process_enrichment_job(job.id)

        derived_jobs = list(
            await session.scalars(
                select(IndexingJob).where(IndexingJob.sync_run_id == sync_run.id)
            )
        )
        for job in derived_jobs:
            if job.status != "done":
                await search_service.process_indexing_job(job.id)

        response = await search_service.search(ArchiveSearchRequest(query="лицей", limit=10))
        assert response.items
        assert any("derived_text" in item.matched_projection_kinds for item in response.items)
        assert any(item.snippet_source in {"summary", "transcript", "text"} for item in response.items)
