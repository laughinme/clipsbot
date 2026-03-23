from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from core.config import get_settings
from core.errors import ConflictError, NotFoundError, UnauthorizedError
from database.relational_db import BrowserLoginChallenge, BrowserLoginChallengeInterface, UoW

from ..telegram_auth import TelegramAuthService


class BrowserAuthService:
    def __init__(
        self,
        *,
        uow: UoW,
        challenge_repo: BrowserLoginChallengeInterface,
        telegram_auth_service: TelegramAuthService,
    ) -> None:
        self.uow = uow
        self.challenge_repo = challenge_repo
        self.telegram_auth_service = telegram_auth_service
        self.settings = get_settings()

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_hex(24)

    def _deep_link_for_token(self, token: str) -> str:
        username = self.settings.TELEGRAM_BOT_USERNAME.strip().lstrip("@")
        payload = f"login_{token}"
        return f"https://t.me/{username}?start={payload}"

    async def start(self) -> BrowserLoginChallenge:
        expires_at = datetime.now(UTC) + timedelta(minutes=5)
        challenge = BrowserLoginChallenge(
            token=self._generate_token(),
            status="pending",
            expires_at=expires_at,
        )
        await self.challenge_repo.add(challenge)
        await self.uow.commit()
        await self.uow.session.refresh(challenge)
        return challenge

    async def get_status(self, token: str) -> BrowserLoginChallenge:
        challenge = await self.challenge_repo.get_by_token(token)
        if challenge is None:
            raise NotFoundError("Browser login challenge not found")

        if challenge.status in {"pending", "approved"} and challenge.expires_at <= datetime.now(UTC):
            challenge.status = "expired"
            await self.uow.commit()
            await self.uow.session.refresh(challenge)

        return challenge

    async def confirm(
        self,
        *,
        token: str,
        telegram_user: dict[str, object],
    ) -> BrowserLoginChallenge:
        challenge = await self.get_status(token)
        if challenge.status == "expired":
            raise UnauthorizedError("Browser login challenge has expired")
        if challenge.status == "consumed":
            raise ConflictError("Browser login challenge has already been used")

        challenge.status = "approved"
        challenge.approved_at = datetime.now(UTC)
        challenge.telegram_user_payload = telegram_user
        await self.uow.commit()
        await self.uow.session.refresh(challenge)
        return challenge

    async def complete(self, token: str) -> tuple[str, str, str]:
        challenge = await self.get_status(token)
        if challenge.status == "expired":
            raise UnauthorizedError("Browser login challenge has expired")
        if challenge.status == "consumed":
            raise ConflictError("Browser login challenge has already been used")
        if challenge.status != "approved" or not challenge.telegram_user_payload:
            raise UnauthorizedError("Browser login challenge is not approved yet")

        access, refresh, csrf, _ = await self.telegram_auth_service.authenticate_telegram_user(
            challenge.telegram_user_payload,
            notify_new_user=True,
        )
        challenge.status = "consumed"
        challenge.consumed_at = datetime.now(UTC)
        await self.uow.commit()
        return access, refresh, csrf

    def build_start_response_payload(self, challenge: BrowserLoginChallenge) -> dict[str, object]:
        return {
            "challenge_token": challenge.token,
            "status": challenge.status,
            "expires_at": challenge.expires_at,
            "telegram_deep_link": self._deep_link_for_token(challenge.token),
            "telegram_bot_username": self.settings.TELEGRAM_BOT_USERNAME.strip().lstrip("@"),
        }

    @staticmethod
    def build_status_response_payload(challenge: BrowserLoginChallenge) -> dict[str, object]:
        payload = challenge.telegram_user_payload or {}
        approved_display_name = " ".join(
            part
            for part in [
                str(payload.get("first_name") or "").strip(),
                str(payload.get("last_name") or "").strip(),
            ]
            if part
        ).strip() or (str(payload.get("username") or "").strip() or None)

        approved_telegram_id_raw = payload.get("id")
        approved_telegram_id = int(approved_telegram_id_raw) if approved_telegram_id_raw is not None else None

        return {
            "challenge_token": challenge.token,
            "status": challenge.status,
            "expires_at": challenge.expires_at,
            "approved_at": challenge.approved_at,
            "approved_telegram_id": approved_telegram_id,
            "approved_telegram_username": payload.get("username"),
            "approved_display_name": approved_display_name,
        }
