import logging


logger = logging.getLogger(__name__)


class NoopNotificationService:
    async def send_text(self, message: str) -> None:
        logger.info("Notification skipped (noop provider): %s", message)
