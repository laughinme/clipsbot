from fastapi import APIRouter


def get_api_routers() -> APIRouter:
    from .v1 import get_v1_router
    
    router = APIRouter(prefix="/api")
    
    router.include_router(get_v1_router())
    
    return router
