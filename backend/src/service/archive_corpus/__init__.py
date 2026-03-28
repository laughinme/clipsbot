from functools import lru_cache

from fastapi import Depends

from broker import BrokerPublisher, get_broker_publisher
from core.config import Settings, get_settings
from database.relational_db import (
    CorpusAssetInterface,
    CorpusItemInterface,
    CorpusProjectionInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    SyncRunInterface,
    UoW,
    get_uow,
)
from service.media import MediaStorageService, get_media_storage_service
from service.archive_enrichments import ArchiveEnrichmentService, get_archive_enrichment_service

from .adapters.base import SourceAdapterRegistry
from .adapters.telegram_desktop_export import TelegramDesktopExportAdapter
from .source_service import ArchiveSourceService


@lru_cache(maxsize=1)
def get_source_adapter_registry() -> SourceAdapterRegistry:
    settings = get_settings()
    return SourceAdapterRegistry(
        adapters=[
            TelegramDesktopExportAdapter(settings),
        ]
    )


async def get_archive_source_service(
    uow: UoW = Depends(get_uow),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
    broker: BrokerPublisher = Depends(get_broker_publisher),
    enrichment_service: ArchiveEnrichmentService = Depends(get_archive_enrichment_service),
    settings: Settings = Depends(get_settings),
) -> ArchiveSourceService:
    return ArchiveSourceService(
        uow=uow,
        source_repo=SourceConnectionInterface(uow.session),
        sync_run_repo=SyncRunInterface(uow.session),
        corpus_item_repo=CorpusItemInterface(uow.session),
        corpus_asset_repo=CorpusAssetInterface(uow.session),
        corpus_projection_repo=CorpusProjectionInterface(uow.session),
        indexing_job_repo=IndexingJobInterface(uow.session),
        media_storage=media_storage,
        broker=broker,
        settings=settings,
        adapter_registry=get_source_adapter_registry(),
        enrichment_service=enrichment_service,
    )


from .source_service import ArchiveSourceService
