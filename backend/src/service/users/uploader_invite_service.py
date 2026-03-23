from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID

from core.config import get_settings
from core.errors import ConflictError, NotFoundError, UnauthorizedError
from database.relational_db import UoW, UploaderInvite, UploaderInviteInterface, User, UserInterface
from domain.users import UploaderInviteModel
from service.auth.telegram_auth import TelegramAuthService


class UploaderInviteService:
    def __init__(
        self,
        *,
        uow: UoW,
        invite_repo: UploaderInviteInterface,
        user_repo: UserInterface,
        telegram_auth_service: TelegramAuthService,
    ) -> None:
        self.uow = uow
        self.invite_repo = invite_repo
        self.user_repo = user_repo
        self.telegram_auth_service = telegram_auth_service
        self.settings = get_settings()

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_hex(24)

    def _deep_link_for_token(self, token: str) -> str:
        username = self.settings.TELEGRAM_BOT_USERNAME.strip().lstrip("@")
        payload = quote(f"invite_{token}", safe="")
        return f"https://t.me/{username}?start={payload}"

    async def _refresh_expired(self) -> None:
        updated = await self.invite_repo.expire_pending()
        if updated:
            await self.uow.commit()

    def _serialize(self, invite: UploaderInvite) -> UploaderInviteModel:
        return UploaderInviteModel(
            id=invite.id,
            status=invite.status,
            invite_link=self._deep_link_for_token(invite.token),
            expires_at=invite.expires_at,
            revoked_at=invite.revoked_at,
            consumed_at=invite.consumed_at,
            created_by_user_id=invite.created_by_user_id,
            consumed_by_user_id=invite.consumed_by_user_id,
            created_at=invite.created_at,
            updated_at=invite.updated_at,
        )

    async def create(self, created_by: User) -> UploaderInviteModel:
        await self._refresh_expired()
        invite = UploaderInvite(
            token=self._generate_token(),
            status="pending",
            created_by_user_id=created_by.id,
            expires_at=datetime.now(UTC) + timedelta(hours=self.settings.UPLOADER_INVITE_TTL_HOURS),
        )
        await self.invite_repo.add(invite)
        await self.uow.commit()
        await self.uow.session.refresh(invite)
        return self._serialize(invite)

    async def list_recent(self, *, limit: int = 20) -> list[UploaderInviteModel]:
        await self._refresh_expired()
        invites = await self.invite_repo.list_recent(limit=limit)
        return [self._serialize(invite) for invite in invites]

    async def revoke(self, invite_id: UUID | str) -> UploaderInviteModel:
        invite = await self.invite_repo.get_by_id(invite_id)
        if invite is None:
            raise NotFoundError("Uploader invite not found")
        if invite.status == "consumed":
            raise ConflictError("Uploader invite has already been consumed")

        invite.status = "revoked"
        invite.revoked_at = datetime.now(UTC)
        await self.uow.commit()
        await self.uow.session.refresh(invite)
        return self._serialize(invite)

    async def consume(self, *, token: str, telegram_user: dict[str, object]) -> UploaderInviteModel:
        await self._refresh_expired()
        invite = await self.invite_repo.get_by_token(token)
        if invite is None:
            raise NotFoundError("Uploader invite not found")
        if invite.status == "expired":
            raise UnauthorizedError("Uploader invite has expired")
        if invite.status == "revoked":
            raise ConflictError("Uploader invite has been revoked")
        if invite.status == "consumed":
            raise ConflictError("Uploader invite has already been used")

        user, _ = await self.telegram_auth_service.upsert_trusted_telegram_user(telegram_user)
        user = await self.user_repo.get_by_id(user.id) or user
        if "uploader" not in user.role_slugs:
            current_role_slugs = list(dict.fromkeys([*user.role_slugs, "uploader"]))
            roles = await self.telegram_auth_service.role_repo.get_by_slugs(current_role_slugs)
            await self.user_repo.assign_roles(user, roles)
            user.bump_auth_version()

        invite.status = "consumed"
        invite.consumed_at = datetime.now(UTC)
        invite.consumed_by_user_id = user.id
        await self.uow.commit()
        await self.uow.session.refresh(invite)
        return self._serialize(invite)
