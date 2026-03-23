from fastapi import APIRouter


def get_auth_routers() -> APIRouter:
    from .browser import router as browser_router
    from .login import router as logout_router
    from .refresh import router as refresh_router
    from .telegram import router as telegram_router
    
    router = APIRouter(
        prefix='/auth', 
        tags=['Auth'],
        responses={
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            429: {"description": "Too Many Requests"}
        },
    )
    
    router.include_router(browser_router)
    router.include_router(logout_router)
    router.include_router(refresh_router)
    router.include_router(telegram_router)
    
    return router
