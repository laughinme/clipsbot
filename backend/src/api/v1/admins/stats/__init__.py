from fastapi import APIRouter


def get_stats_router() -> APIRouter:
    from .users import router as users_router
    
    router = APIRouter(prefix='/stats')

    router.include_router(users_router)
    
    return router
