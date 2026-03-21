from fastapi import APIRouter


def get_user_id_router() -> APIRouter:
    from .ban import router as ban_router
    from .roles import router as roles_router

    router = APIRouter(prefix='/{user_id}')
    
    router.include_router(ban_router)
    router.include_router(roles_router)
    
    return router
