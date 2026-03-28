from fastapi import Depends

from core.config import Settings, get_settings
from database.relational_db import (
    CorpusItemInterface,
    CorpusProjectionInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    UoW,
    get_uow,
)
from integrations.embeddings import EmbeddingProvider, get_embedding_provider
from integrations.qdrant import QdrantService, get_qdrant_service
from service.media import MediaStorageService, get_media_storage_service

from .search_service import SemanticSearchService


async def get_semantic_search_service(
    uow: UoW = Depends(get_uow),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    qdrant: QdrantService = Depends(get_qdrant_service),
    settings: Settings = Depends(get_settings),
) -> SemanticSearchService:
    return SemanticSearchService(
        uow=uow,
        source_repo=SourceConnectionInterface(uow.session),
        corpus_item_repo=CorpusItemInterface(uow.session),
        corpus_projection_repo=CorpusProjectionInterface(uow.session),
        indexing_job_repo=IndexingJobInterface(uow.session),
        embeddings=embeddings,
        qdrant=qdrant,
        media_storage=media_storage,
        settings=settings,
    )


from .search_service import SemanticSearchService
