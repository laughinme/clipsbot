from typing import Annotated

from fastapi import Depends

from database.relational_db import RolesInterface, UoW, UserInterface, get_uow
from service.media import MediaStorageService, get_media_storage_service
from service.notifications import NotificationService, get_notification_service

from ..tokens import TokenService, get_token_service
from .telegram_service import TelegramAuthService


async def get_telegram_auth_service(
    uow: Annotated[UoW, Depends(get_uow)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    notification_service: Annotated[NotificationService, Depends(get_notification_service)],
    media_storage: Annotated[MediaStorageService, Depends(get_media_storage_service)],
) -> TelegramAuthService:
    return TelegramAuthService(
        uow=uow,
        user_repo=UserInterface(uow.session),
        role_repo=RolesInterface(uow.session),
        token_service=token_service,
        notification_service=notification_service,
        media_storage=media_storage,
    )


from .telegram_service import TelegramAuthService
