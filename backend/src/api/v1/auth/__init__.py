from fastapi import APIRouter, Depends

from core.rate_limit import AUTH_LIMITER_STATE_KEY, build_rate_dependency

auth_rate_limit = build_rate_dependency(AUTH_LIMITER_STATE_KEY)


def get_auth_routers() -> APIRouter:
    from .registration import router as register_router
    from .login import router as login_router
    from .refresh import router as refresh_router
    
    router = APIRouter(
        prefix='/auth', 
        tags=['Auth'],
        responses={
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            429: {"description": "Too Many Requests"}
        },
        dependencies=[Depends(auth_rate_limit)]
    )
    
    router.include_router(register_router)
    router.include_router(login_router)
    router.include_router(refresh_router)
    
    return router
