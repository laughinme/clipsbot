from fastapi import APIRouter


def get_admins_router() -> APIRouter:
    from .clips import get_clips_router
    from .roles import router as roles_router
    from .uploader_invites import router as uploader_invites_router
    from .users import get_users_router
    from .stats import get_stats_router
    
    router = APIRouter(prefix='/admins', tags=['Admins'])

    router.include_router(get_clips_router())
    router.include_router(roles_router)
    router.include_router(uploader_invites_router)
    router.include_router(get_users_router())
    router.include_router(get_stats_router())
    
    return router
