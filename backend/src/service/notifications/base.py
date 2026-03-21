from typing import Protocol


class NotificationService(Protocol):
    async def send_text(self, message: str) -> None: ...
