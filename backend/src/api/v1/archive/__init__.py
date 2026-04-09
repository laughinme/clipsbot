from fastapi import APIRouter


def get_archive_router() -> APIRouter:
    from .enrichments import router as enrichments_router
    from .items import router as items_router
    from .sources import router as sources_router
    from .search import router as search_router

    router = APIRouter(prefix="/archive", tags=["Archive"])
    router.include_router(sources_router)
    router.include_router(search_router)
    router.include_router(items_router)
    router.include_router(enrichments_router)
    return router
