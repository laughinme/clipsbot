from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from core.config import get_settings
from service.auth.tokens import TokenService


class FakeCacheRepo:
    def __init__(self):
        self.storage: dict[str, str] = {}

    async def set(self, name: str, value: str, ttl: int | None = None) -> None:
        self.storage[name] = value

    async def exists(self, *names: str) -> int:
        return sum(1 for name in names if name in self.storage)


class FakeUserRepo:
    def __init__(self, users: dict[str, SimpleNamespace]):
        self.users = users

    async def get_by_id(self, user_id: str):
        return self.users.get(str(user_id))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_issue_tokens_contains_expected_claims():
    settings = get_settings()
    user = SimpleNamespace(id=uuid4(), auth_version=3)
    cache = FakeCacheRepo()
    user_repo = FakeUserRepo({str(user.id): user})
    svc = TokenService(cache, user_repo)

    access, refresh, _ = await svc.issue_tokens(user, "mobile")

    access_payload = jwt.decode(
        access,
        settings.JWT_PUBLIC_KEY,
        algorithms=[settings.JWT_ALGO],
        options={"verify_exp": False},
    )
    refresh_payload = jwt.decode(
        refresh,
        settings.JWT_PUBLIC_KEY,
        algorithms=[settings.JWT_ALGO],
        options={"verify_exp": False},
    )

    assert access_payload["sub"] == str(user.id)
    assert access_payload["typ"] == "access"
    assert access_payload["av"] == 3
    assert access_payload["src"] == "mobile"

    assert refresh_payload["sub"] == str(user.id)
    assert refresh_payload["typ"] == "refresh"
    assert refresh_payload["av"] == 3
    assert refresh_payload["src"] == "mobile"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refresh_rotates_and_blocks_old_refresh_jti():
    user = SimpleNamespace(id=uuid4(), auth_version=1)
    cache = FakeCacheRepo()
    user_repo = FakeUserRepo({str(user.id): user})
    svc = TokenService(cache, user_repo)

    _, refresh, _ = await svc.issue_tokens(user, "mobile")
    rotated = await svc.refresh_tokens(refresh)
    reused = await svc.refresh_tokens(refresh)

    assert rotated is not None
    assert reused is None
