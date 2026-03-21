from fastapi import APIRouter


def get_users_router() -> APIRouter:
    from .list import router as list_router
    from .user_id import get_user_id_router

    router = APIRouter(prefix='/users')
    
    router.include_router(list_router)
    router.include_router(get_user_id_router())
    
    return router
