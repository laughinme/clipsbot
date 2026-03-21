import asyncio
import json
import urllib.error
import urllib.request


class TelegramNotificationService:
    def __init__(self, *, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def _post(self, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10):
                return
        except urllib.error.URLError:
            return

    async def send_text(self, message: str) -> None:
        await asyncio.to_thread(self._post, message)
