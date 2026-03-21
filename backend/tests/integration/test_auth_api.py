from uuid import uuid4

import pytest
from faker import Faker
from httpx import AsyncClient

from tests.helpers import auth_header

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_integration_state"),
]


def _mobile_headers() -> dict[str, str]:
    return {"X-Client": "mobile"}


@pytest.mark.asyncio
async def test_register_login_refresh_logout_flow(
    client: AsyncClient,
    faker: Faker,
):
    suffix = uuid4().hex[:8]
    payload = {
        "email": f"user_{suffix}@example.com",
        "password": faker.password(length=12),
        "username": f"user_{suffix}",
    }

    register = await client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=_mobile_headers(),
    )
    assert register.status_code == 201
    register_data = register.json()
    assert register_data["access_token"]
    assert register_data["refresh_token"]

    profile = await client.get(
        "/api/v1/users/me",
        headers=auth_header(register_data["access_token"]),
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == payload["email"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
        headers=_mobile_headers(),
    )
    assert login.status_code == 200
    login_data = login.json()
    assert login_data["access_token"]
    assert login_data["refresh_token"]

    refresh = await client.post(
        "/api/v1/auth/refresh",
        headers=auth_header(login_data["refresh_token"]),
    )
    assert refresh.status_code == 200
    refresh_data = refresh.json()
    assert refresh_data["access_token"]
    assert refresh_data["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        headers=auth_header(refresh_data["refresh_token"]),
    )
    assert logout.status_code == 200

    refresh_after_logout = await client.post(
        "/api/v1/auth/refresh",
        headers=auth_header(refresh_data["refresh_token"]),
    )
    assert refresh_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_protected_profile_requires_access_token(client: AsyncClient):
    response = await client.get("/api/v1/users/me")
    assert response.status_code in {401, 403}
