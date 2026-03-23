import asyncio
from datetime import datetime
from datetime import UTC
from uuid import UUID

from core.config import get_settings
# from core.rbac import permissions_cache_key
from database.redis import CacheRepo
from domain.users import UserPatch, AvatarPresignResponse
from database.relational_db import (
    LanguagesInterface,
    RolesInterface,
    UserInterface,
    UoW,
    User,
)
from service.media import ALLOWED_AVATAR_CONTENT_TYPES, MediaStorageService
from .exceptions import (
    AvatarObjectNotFoundError,
    AvatarTooLargeError,
    AvatarUnsupportedContentTypeError,
    InvalidAvatarObjectKeyError,
    InvalidCursorError,
    ProtectedAdminRoleError,
    UnknownRolesError,
    UnsupportedAvatarContentTypeError,
)


class UserService:
    def __init__(
        self,
        uow: UoW,
        user_repo: UserInterface,
        lang_repo: LanguagesInterface,
        role_repo: RolesInterface,
        media_storage: MediaStorageService,
        cache_repo: CacheRepo | None = None,
    ):
        self.uow = uow
        self.user_repo = user_repo
        self.lang_repo = lang_repo
        self.role_repo = role_repo
        self.media_storage = media_storage
        self.cache_repo = cache_repo
        self.settings = get_settings()
        
    async def get_user(self, user_id: UUID | str) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.user_repo.get_by_telegram_id(telegram_id)
        
    async def patch_user(self, payload: UserPatch, user: User):
        data = payload.model_dump(exclude_none=True)
        
        for field, value in data.items():
            setattr(user, field, value)
            
        await self.uow.commit()
            
        await self.uow.session.refresh(user)

    async def create_avatar_presign(
        self,
        *,
        user: User,
        filename: str,
        content_type: str,
    ) -> AvatarPresignResponse:
        if content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise UnsupportedAvatarContentTypeError(list(ALLOWED_AVATAR_CONTENT_TYPES))

        object_key = self.media_storage.build_avatar_key(user.id, filename, content_type)
        upload_url = self.media_storage.create_presigned_upload_url(
            bucket=self.settings.STORAGE_PUBLIC_BUCKET,
            key=object_key,
            content_type=content_type,
            expires_in=self.settings.STORAGE_PRESIGN_EXPIRES_SEC,
        )
        public_url = self.media_storage.build_public_url(
            bucket=self.settings.STORAGE_PUBLIC_BUCKET,
            key=object_key,
        )

        return AvatarPresignResponse(
            object_key=object_key,
            upload_url=upload_url,
            public_url=public_url,
            expires_in=self.settings.STORAGE_PRESIGN_EXPIRES_SEC,
        )

    async def confirm_avatar_upload(self, *, user: User, object_key: str) -> None:
        expected_prefix = f"avatars/{user.id}/"
        if not object_key.startswith(expected_prefix):
            raise InvalidAvatarObjectKeyError()

        stat = await asyncio.to_thread(
            lambda: self.media_storage.get_object_stat(
                bucket=self.settings.STORAGE_PUBLIC_BUCKET,
                key=object_key,
            ),
        )
        if stat is None:
            raise AvatarObjectNotFoundError()

        if stat.content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise AvatarUnsupportedContentTypeError()

        max_size_bytes = self.settings.MAX_PHOTO_SIZE * 1024 * 1024
        if stat.size_bytes > max_size_bytes:
            raise AvatarTooLargeError(self.settings.MAX_PHOTO_SIZE)

        previous_avatar_key = user.avatar_key
        user.avatar_key = object_key
        await self.uow.commit()
        await self.uow.session.refresh(user)

        if previous_avatar_key and previous_avatar_key != object_key:
            await asyncio.to_thread(
                lambda: self.media_storage.delete_object(
                    bucket=self.settings.STORAGE_PUBLIC_BUCKET,
                    key=previous_avatar_key,
                ),
            )

    async def remove_avatar(self, *, user: User) -> None:
        if not user.avatar_key:
            return

        avatar_key = user.avatar_key
        user.avatar_key = None
        await self.uow.commit()
        await self.uow.session.refresh(user)

        await asyncio.to_thread(
            lambda: self.media_storage.delete_object(
                bucket=self.settings.STORAGE_PUBLIC_BUCKET,
                key=avatar_key,
            ),
        )

    async def admin_list_users(
        self,
        *,
        banned: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[User], str | None]:
        cursor_created_at = None
        cursor_id = None
        if cursor:
            try:
                ts_str, id_str = cursor.split("_", 1)
                cursor_created_at = datetime.fromisoformat(ts_str)
                cursor_id = UUID(id_str)
            except Exception:
                raise InvalidCursorError()

        users = await self.user_repo.admin_list_users(
            banned=banned,
            search=search,
            limit=limit,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )

        next_cursor = None
        if len(users) == limit:
            last = users[-1]
            if last.created_at is None:
                next_cursor = None
            else:
                next_cursor = f"{last.created_at.isoformat()}_{last.id}"

        return users, next_cursor

    async def admin_set_ban(self, target: User, banned: bool) -> User:
        target.banned = banned
        target.bump_auth_version()
        await self.uow.commit()
        await self.uow.session.refresh(target)
        # await self._invalidate_permissions_cache(target.id, target.auth_version)
        return target

    async def list_languages(self, search: str, limit: int):
        return await self.lang_repo.search(search, limit)

    async def list_roles(
        self,
        *,
        search: str | None = None,
        limit: int | None = None,
    ):
        return await self.role_repo.list_roles(search=search, limit=limit)

    async def admin_assign_roles(
        self,
        target: User,
        role_slugs: list[str],
    ) -> User:
        unique_slugs = list(dict.fromkeys(role_slugs))
        if (
            target.telegram_id is not None
            and target.telegram_id in self.settings.bootstrap_admin_telegram_ids
            and "admin" not in unique_slugs
        ):
            raise ProtectedAdminRoleError()

        roles = await self.role_repo.get_by_slugs(unique_slugs)
        found_slugs = {role.slug for role in roles}
        missing = [slug for slug in unique_slugs if slug not in found_slugs]
        if missing:
            raise UnknownRolesError(missing)

        await self.user_repo.assign_roles(target, roles)
        target.bump_auth_version()
        await self.uow.commit()
        await self.uow.session.refresh(target)

        # await self._invalidate_permissions_cache(target.id, target.auth_version)
        return target

    # async def _invalidate_permissions_cache(
    #     self,
    #     user_id: UUID | str,
    #     previous_version: int | None,
    # ) -> None:
    #     if not self.cache_repo or previous_version is None:
    #         return
    #     cache_key = permissions_cache_key(user_id, previous_version)
    #     await self.cache_repo.delete(cache_key)
