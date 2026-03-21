from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.errors import DomainError
from service.users.user_service import UserService


class FakeSession:
    async def refresh(self, _obj) -> None:
        return None


class FakeUoW:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeMediaStorage:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def build_avatar_key(self, user_id, filename: str, content_type: str) -> str:
        return f"avatars/{user_id}/avatar.jpg"

    def create_presigned_upload_url(self, *, bucket: str, key: str, content_type: str, expires_in: int | None = None) -> str:
        return f"http://localhost/{bucket}/{key}?signature=test"

    def build_public_url(self, *, bucket: str, key: str) -> str:
        return f"http://localhost/{bucket}/{key}"

    def get_object_stat(self, *, bucket: str, key: str):
        return SimpleNamespace(size_bytes=1024, content_type="image/jpeg")

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.deleted.append((bucket, key))


class DummyRepo:
    async def search(self, *_args, **_kwargs):
        return []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_avatar_presign_returns_upload_and_public_urls():
    uow = FakeUoW()
    media = FakeMediaStorage()
    svc = UserService(
        uow=uow,
        user_repo=DummyRepo(),
        lang_repo=DummyRepo(),
        role_repo=DummyRepo(),
        media_storage=media,
        cache_repo=None,
    )
    user = SimpleNamespace(id=uuid4())

    response = await svc.create_avatar_presign(
        user=user,
        filename="avatar.png",
        content_type="image/png",
    )

    assert response.object_key.startswith(f"avatars/{user.id}/")
    assert response.upload_url.startswith("http://localhost/")
    assert response.public_url.startswith("http://localhost/")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirm_avatar_upload_rejects_foreign_object_key_prefix():
    uow = FakeUoW()
    media = FakeMediaStorage()
    svc = UserService(
        uow=uow,
        user_repo=DummyRepo(),
        lang_repo=DummyRepo(),
        role_repo=DummyRepo(),
        media_storage=media,
        cache_repo=None,
    )
    user = SimpleNamespace(id=uuid4(), avatar_key=None)

    with pytest.raises(DomainError) as exc:
        await svc.confirm_avatar_upload(
            user=user,
            object_key=f"avatars/{uuid4()}/evil.jpg",
        )

    assert exc.value.status_code == 400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_confirm_and_remove_avatar_updates_user_and_deletes_previous_file():
    uow = FakeUoW()
    media = FakeMediaStorage()
    svc = UserService(
        uow=uow,
        user_repo=DummyRepo(),
        lang_repo=DummyRepo(),
        role_repo=DummyRepo(),
        media_storage=media,
        cache_repo=None,
    )
    user = SimpleNamespace(id=uuid4(), avatar_key=f"avatars/{uuid4()}/old.jpg")
    new_key = f"avatars/{user.id}/new.jpg"

    await svc.confirm_avatar_upload(user=user, object_key=new_key)

    assert user.avatar_key == new_key
    assert uow.commits == 1
    assert media.deleted[-1][1].endswith("old.jpg")

    await svc.remove_avatar(user=user)

    assert user.avatar_key is None
    assert uow.commits == 2
    assert media.deleted[-1][1] == new_key
