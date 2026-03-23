from fastapi import APIRouter


def get_internal_router() -> APIRouter:
    from .bot import router as bot_router

    router = APIRouter(prefix="/internal", tags=["Internal"])
    router.include_router(bot_router)
    return router
