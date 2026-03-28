from fastapi import Depends

from broker import BrokerPublisher, get_broker_publisher
from core.config import Settings, get_settings
from database.relational_db import (
    CorpusEnrichmentInterface,
    CorpusItemInterface,
    CorpusProjectionInterface,
    EnrichmentJobInterface,
    EnrichmentRunInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    UoW,
    get_uow,
)
from integrations.gcs_staging import GcsStagingService, get_gcs_staging_service
from service.media import MediaStorageService, get_media_storage_service

from .providers import (
    ArchiveEnrichmentProviders,
    SpeechV2TranscriptProvider,
    StubOcrProvider,
    StubSummaryProvider,
    StubTranscriptProvider,
    VertexSummaryProvider,
    VisionOcrProvider,
)
from .service import ArchiveEnrichmentService


def get_archive_enrichment_providers(
    settings: Settings | None = None,
    gcs_staging: GcsStagingService | None = None,
) -> ArchiveEnrichmentProviders:
    settings = settings or get_settings()
    gcs_staging = gcs_staging or get_gcs_staging_service()
    ocr = VisionOcrProvider(settings) if settings.OCR_PROVIDER == "vision" else StubOcrProvider()
    transcript = (
        SpeechV2TranscriptProvider(settings, gcs_staging)
        if settings.TRANSCRIPT_PROVIDER == "speech_v2"
        else StubTranscriptProvider()
    )
    summary = VertexSummaryProvider(settings) if settings.SUMMARY_PROVIDER == "vertex" else StubSummaryProvider()
    return ArchiveEnrichmentProviders(ocr=ocr, transcript=transcript, summary=summary)


async def get_archive_enrichment_service(
    uow: UoW = Depends(get_uow),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
    gcs_staging: GcsStagingService = Depends(get_gcs_staging_service),
    broker: BrokerPublisher = Depends(get_broker_publisher),
    settings: Settings = Depends(get_settings),
) -> ArchiveEnrichmentService:
    return ArchiveEnrichmentService(
        uow=uow,
        source_repo=SourceConnectionInterface(uow.session),
        corpus_item_repo=CorpusItemInterface(uow.session),
        corpus_projection_repo=CorpusProjectionInterface(uow.session),
        corpus_enrichment_repo=CorpusEnrichmentInterface(uow.session),
        enrichment_run_repo=EnrichmentRunInterface(uow.session),
        enrichment_job_repo=EnrichmentJobInterface(uow.session),
        indexing_job_repo=IndexingJobInterface(uow.session),
        media_storage=media_storage,
        broker=broker,
        providers=get_archive_enrichment_providers(settings=settings, gcs_staging=gcs_staging),
        settings=settings,
    )


from .service import ArchiveEnrichmentService
