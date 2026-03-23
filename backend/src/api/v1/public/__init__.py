from fastapi import APIRouter


def get_public_router() -> APIRouter:
    from .clips import router as clips_router

    router = APIRouter(prefix="/public", tags=["Public"])
    router.include_router(clips_router)
    return router
