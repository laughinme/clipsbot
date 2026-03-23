from typing import Annotated

from fastapi import Depends

from database.relational_db import BrowserLoginChallengeInterface, RolesInterface, UoW, UserInterface, get_uow
from service.media import MediaStorageService, get_media_storage_service
from service.notifications import NotificationService, get_notification_service

from ..telegram_auth import TelegramAuthService
from ..tokens import TokenService, get_token_service
from .browser_service import BrowserAuthService


async def get_browser_auth_service(
    uow: Annotated[UoW, Depends(get_uow)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    notification_service: Annotated[NotificationService, Depends(get_notification_service)],
    media_storage: Annotated[MediaStorageService, Depends(get_media_storage_service)],
) -> BrowserAuthService:
    telegram_auth_service = TelegramAuthService(
        uow=uow,
        user_repo=UserInterface(uow.session),
        role_repo=RolesInterface(uow.session),
        token_service=token_service,
        notification_service=notification_service,
        media_storage=media_storage,
    )
    return BrowserAuthService(
        uow=uow,
        challenge_repo=BrowserLoginChallengeInterface(uow.session),
        telegram_auth_service=telegram_auth_service,
    )


from .browser_service import BrowserAuthService
