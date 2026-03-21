from fastapi import Depends

from core.config import Settings, get_settings
from .base import NotificationService
from .noop import NoopNotificationService
from .telegram import TelegramNotificationService


def get_notification_service(
    settings: Settings = Depends(get_settings),
) -> NotificationService:
    if settings.NOTIFICATIONS_PROVIDER == "telegram":
        return TelegramNotificationService(
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            chat_id=settings.TELEGRAM_CHAT_ID,
        )

    return NoopNotificationService()
