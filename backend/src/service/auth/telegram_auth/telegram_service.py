from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen

from core.config import get_settings
from core.errors import ForbiddenError, UnauthorizedError
from database.relational_db import RolesInterface, UoW, User, UserInterface
from service.media import MediaStorageService
from service.notifications import NotificationService

from ..tokens import TokenService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramAvatarPayload:
    file_unique_id: str
    filename: str
    content_type: str
    payload: bytes


class TelegramAuthService:
    def __init__(
        self,
        *,
        uow: UoW,
        user_repo: UserInterface,
        role_repo: RolesInterface,
        token_service: TokenService,
        notification_service: NotificationService,
        media_storage: MediaStorageService,
    ) -> None:
        self.uow = uow
        self.user_repo = user_repo
        self.role_repo = role_repo
        self.token_service = token_service
        self.notification_service = notification_service
        self.media_storage = media_storage
        self.settings = get_settings()

    @staticmethod
    def _display_name_from_telegram_user(telegram_user: dict[str, object]) -> str | None:
        first_name = telegram_user.get("first_name")
        last_name = telegram_user.get("last_name")
        username = telegram_user.get("username")

        name = " ".join(
            part.strip()
            for part in (
                str(first_name).strip() if isinstance(first_name, str) else "",
                str(last_name).strip() if isinstance(last_name, str) else "",
            )
            if part.strip()
        ).strip()
        if name:
            return name

        if isinstance(username, str) and username.strip():
            return username.strip()

        return None

    async def _resolve_assignment_role_slugs(self, telegram_id: int, current_role_slugs: list[str] | None = None) -> list[str]:
        desired: list[str] = list(current_role_slugs or [])

        default_slug = self.settings.AUTH_DEFAULT_ROLE_SLUG
        if default_slug and default_slug not in desired:
            desired.append(default_slug)

        if telegram_id in self.settings.bootstrap_admin_telegram_ids and "admin" not in desired:
            desired.append("admin")

        return desired

    def _validate_init_data(self, init_data: str) -> dict[str, str]:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        provided_hash = pairs.pop("hash", None)
        if not provided_hash:
            raise UnauthorizedError("Telegram auth hash is missing")

        auth_date_raw = pairs.get("auth_date")
        if not auth_date_raw:
            raise UnauthorizedError("Telegram auth_date is missing")

        secret_key = hmac.new(
            b"WebAppData",
            self.settings.TELEGRAM_BOT_TOKEN.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(provided_hash, expected_hash):
            raise UnauthorizedError("Invalid Telegram init data")

        auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=UTC)
        age_seconds = (datetime.now(UTC) - auth_date).total_seconds()
        if age_seconds > self.settings.TELEGRAM_AUTH_MAX_AGE_SEC:
            raise UnauthorizedError("Telegram init data has expired")

        return pairs

    def _bot_api_url(self, method: str, **params: object) -> str:
        base = f"https://api.telegram.org/bot{self.settings.TELEGRAM_BOT_TOKEN}/{method}"
        if not params:
            return base
        return f"{base}?{urlencode(params)}"

    def _download_bytes(self, url: str) -> tuple[bytes, str | None]:
        request = Request(url, headers={"User-Agent": "ClipsBot/1.0"})
        with urlopen(request, timeout=15) as response:
            content_type = response.headers.get_content_type()
            return response.read(), content_type

    def _fetch_json(self, url: str) -> dict[str, object]:
        request = Request(url, headers={"User-Agent": "ClipsBot/1.0"})
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_telegram_avatar(self, telegram_id: int) -> TelegramAvatarPayload | None:
        photos_response = self._fetch_json(
            self._bot_api_url("getUserProfilePhotos", user_id=telegram_id, offset=0, limit=1),
        )
        if not photos_response.get("ok"):
            return None

        photos_result = photos_response.get("result")
        if not isinstance(photos_result, dict):
            return None

        photos = photos_result.get("photos")
        if not isinstance(photos, list) or not photos:
            return None

        first_photo_set = photos[0]
        if not isinstance(first_photo_set, list) or not first_photo_set:
            return None

        largest = first_photo_set[-1]
        if not isinstance(largest, dict):
            return None

        file_id = str(largest.get("file_id") or "")
        file_unique_id = str(largest.get("file_unique_id") or "")
        if not file_id or not file_unique_id:
            return None

        file_response = self._fetch_json(self._bot_api_url("getFile", file_id=file_id))
        if not file_response.get("ok"):
            return None

        file_result = file_response.get("result")
        if not isinstance(file_result, dict):
            return None

        file_path = str(file_result.get("file_path") or "")
        if not file_path:
            return None

        download_url = f"https://api.telegram.org/file/bot{self.settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        payload, content_type = self._download_bytes(download_url)
        guessed_type = mimetypes.guess_type(file_path)[0]
        normalized_content_type = content_type or guessed_type or "image/jpeg"
        if normalized_content_type not in {"image/jpeg", "image/png", "image/webp"}:
            normalized_content_type = guessed_type or "image/jpeg"

        filename = file_path.rsplit("/", 1)[-1] or f"{file_unique_id}.jpg"
        return TelegramAvatarPayload(
            file_unique_id=file_unique_id,
            filename=filename,
            content_type=normalized_content_type,
            payload=payload,
        )

    async def _sync_avatar(self, user: User, telegram_id: int) -> None:
        try:
            avatar = await asyncio.to_thread(self._fetch_telegram_avatar, telegram_id)
        except Exception:
            logger.warning("Failed to sync Telegram avatar for user %s", telegram_id, exc_info=True)
            return

        if avatar is None:
            return

        if (
            user.avatar_key
            and user.telegram_avatar_file_unique_id == avatar.file_unique_id
        ):
            return

        object_key = self.media_storage.build_avatar_key(
            user.id,
            avatar.filename,
            avatar.content_type,
        )
        previous_avatar_key = user.avatar_key

        await asyncio.to_thread(
            self.media_storage.put_object_bytes,
            bucket=self.settings.STORAGE_PUBLIC_BUCKET,
            key=object_key,
            payload=avatar.payload,
            content_type=avatar.content_type,
        )

        user.avatar_key = object_key
        user.telegram_avatar_file_unique_id = avatar.file_unique_id
        await self.uow.session.flush()

        if previous_avatar_key and previous_avatar_key != object_key:
            await asyncio.to_thread(
                self.media_storage.delete_object,
                bucket=self.settings.STORAGE_PUBLIC_BUCKET,
                key=previous_avatar_key,
            )

    async def upsert_trusted_telegram_user(
        self,
        telegram_user: dict[str, object],
    ) -> tuple[User, bool]:
        telegram_id = int(telegram_user["id"])
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        is_new_user = user is None
        if user is None:
            user = User(
                telegram_id=telegram_id,
                telegram_username=telegram_user.get("username"),
                username=self._display_name_from_telegram_user(telegram_user),
                last_seen_at=datetime.now(UTC),
            )
            await self.user_repo.add(user)
            await self.uow.session.flush()
            desired_role_slugs = await self._resolve_assignment_role_slugs(telegram_id)
            if desired_role_slugs:
                roles = await self.role_repo.get_by_slugs(desired_role_slugs)
                if roles:
                    await self.user_repo.assign_roles(user, roles)
        else:
            user.telegram_username = telegram_user.get("username")
            user.username = self._display_name_from_telegram_user(telegram_user) or user.username
            user.last_seen_at = datetime.now(UTC)
            current_role_slugs = list(user.role_slugs)
            desired_role_slugs = await self._resolve_assignment_role_slugs(telegram_id, current_role_slugs)
            if set(desired_role_slugs) != set(current_role_slugs):
                roles = await self.role_repo.get_by_slugs(desired_role_slugs)
                await self.user_repo.assign_roles(user, roles)
                user.bump_auth_version()

        await self._sync_avatar(user, telegram_id)
        return user, is_new_user

    async def authenticate_telegram_user(
        self,
        telegram_user: dict[str, object],
        *,
        notify_new_user: bool = True,
    ) -> tuple[str, str, str, User]:
        user, is_new_user = await self.upsert_trusted_telegram_user(telegram_user)

        await self.uow.commit()
        await self.uow.session.refresh(user)

        if is_new_user and notify_new_user:
            await self.notification_service.send_text(
                f"New Telegram user authenticated: {user.telegram_username or user.telegram_id}"
            )

        access, refresh, csrf = await self.token_service.issue_tokens(user, "web")
        return access, refresh, csrf, user

    async def authenticate(self, init_data: str) -> tuple[str, str, str, User]:
        if not self.settings.TELEGRAM_BOT_TOKEN:
            raise ForbiddenError("Telegram bot token is not configured")

        pairs = self._validate_init_data(init_data)
        raw_user = pairs.get("user")
        if not raw_user:
            raise UnauthorizedError("Telegram user payload is missing")

        telegram_user = json.loads(raw_user)
        return await self.authenticate_telegram_user(telegram_user)
