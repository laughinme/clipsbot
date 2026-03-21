from fastapi import APIRouter


def get_misc_router() -> APIRouter:
    from .languages import get_languages_router

    router = APIRouter()

    router.include_router(get_languages_router())

    return router
