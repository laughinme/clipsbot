from fastapi import APIRouter


def get_clip_id_router() -> APIRouter:
    from .delete import router as delete_router
    from .finalize import router as finalize_router
    from .update import router as update_router

    router = APIRouter(prefix="/{clip_id}")
    router.include_router(finalize_router)
    router.include_router(update_router)
    router.include_router(delete_router)
    return router
