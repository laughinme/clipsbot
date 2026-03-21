from fastapi import Depends

from database.redis import CacheRepo, get_redis
from database.relational_db import (
    LanguagesInterface,
    RolesInterface,
    UserInterface,
    UoW,
    get_uow,
)
from service.media import MediaStorageService, get_media_storage_service
from .user_service import UserService


async def get_user_service(
    uow: UoW = Depends(get_uow),
    redis = Depends(get_redis),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
) -> UserService:
    user_repo = UserInterface(uow.session)
    lang_repo = LanguagesInterface(uow.session)
    role_repo = RolesInterface(uow.session)
    cache_repo = CacheRepo(redis) if redis else None
    return UserService(
        uow=uow,
        user_repo=user_repo,
        lang_repo=lang_repo,
        role_repo=role_repo,
        media_storage=media_storage,
        cache_repo=cache_repo,
    )
