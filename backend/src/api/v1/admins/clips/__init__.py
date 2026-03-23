from fastapi import APIRouter


def get_clips_router() -> APIRouter:
    from .list import router as list_router
    from .create import router as create_router
    from .clip_id import get_clip_id_router

    router = APIRouter(prefix="/clips")
    router.include_router(list_router)
    router.include_router(create_router)
    router.include_router(get_clip_id_router())
    return router
