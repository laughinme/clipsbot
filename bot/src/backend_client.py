from __future__ import annotations

from typing import Any

import httpx

from config import get_settings


class BackendClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.INTERNAL_BACKEND_URL,
            headers={"X-Internal-Service-Token": self.settings.INTERNAL_BOT_TOKEN},
            timeout=10.0,
        )

    async def search_clips(self, query: str | None, limit: int = 10) -> list[dict[str, Any]]:
        response = await self._client.get(
            "/bot/clips/search",
            params={"query": query or "", "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("items", [])

    async def confirm_browser_login(
        self,
        *,
        challenge_token: str,
        telegram_id: int,
        telegram_username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> dict[str, Any]:
        response = await self._client.post(
            "/bot/browser-login/confirm",
            json={
                "challenge_token": challenge_token,
                "telegram_id": telegram_id,
                "telegram_username": telegram_username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        response.raise_for_status()
        return response.json()

    async def consume_uploader_invite(
        self,
        *,
        invite_token: str,
        telegram_id: int,
        telegram_username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> dict[str, Any]:
        response = await self._client.post(
            "/bot/uploader-invites/consume",
            json={
                "invite_token": invite_token,
                "telegram_id": telegram_id,
                "telegram_username": telegram_username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
