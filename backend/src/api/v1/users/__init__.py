from fastapi import APIRouter


def get_users_router() -> APIRouter:
    from .me import get_me_router
    
    router = APIRouter(
        prefix='/users',
        tags=['Users'],
        responses={401: {"description": "Not authorized"}}
    )

    router.include_router(get_me_router())
    
    return router
