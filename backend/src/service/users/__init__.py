from fastapi import Depends

from database.redis import CacheRepo, get_redis
from database.relational_db import (
    RolesInterface,
    UploaderInviteInterface,
    LanguagesInterface,
    UserInterface,
    UoW,
    get_uow,
)
from service.media import MediaStorageService, get_media_storage_service
from service.notifications import NotificationService, get_notification_service
from service.auth.telegram_auth import TelegramAuthService
from service.auth.tokens import TokenService, get_token_service
from .user_service import UserService
from .uploader_invite_service import UploaderInviteService


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


async def get_uploader_invite_service(
    uow: UoW = Depends(get_uow),
    token_service: TokenService = Depends(get_token_service),
    notification_service: NotificationService = Depends(get_notification_service),
    media_storage: MediaStorageService = Depends(get_media_storage_service),
) -> UploaderInviteService:
    telegram_auth_service = TelegramAuthService(
        uow=uow,
        user_repo=UserInterface(uow.session),
        role_repo=RolesInterface(uow.session),
        token_service=token_service,
        notification_service=notification_service,
        media_storage=media_storage,
    )
    return UploaderInviteService(
        uow=uow,
        invite_repo=UploaderInviteInterface(uow.session),
        user_repo=UserInterface(uow.session),
        telegram_auth_service=telegram_auth_service,
    )
