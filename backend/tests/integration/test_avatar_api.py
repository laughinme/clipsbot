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
async def test_avatar_presign_upload_confirm_and_delete_flow(client: AsyncClient, faker: Faker):
    suffix = uuid4().hex[:8]
    credentials = {
        "email": f"avatar_{suffix}@example.com",
        "password": faker.password(length=12),
        "username": f"avatar_{suffix}",
    }

    register = await client.post(
        "/api/v1/auth/register",
        json=credentials,
        headers=_mobile_headers(),
    )
    assert register.status_code == 201
    access_token = register.json()["access_token"]

    presign = await client.post(
        "/api/v1/users/me/avatar/presign",
        json={"filename": "avatar.png", "content_type": "image/png"},
        headers=auth_header(access_token),
    )
    assert presign.status_code == 200
    presign_data = presign.json()
    assert presign_data["object_key"].startswith("avatars/")

    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    async with AsyncClient() as external_client:
        upload = await external_client.put(
            presign_data["upload_url"],
            content=png_bytes,
            headers={"Content-Type": "image/png"},
        )

    assert upload.status_code in {200, 204}

    confirm = await client.post(
        "/api/v1/users/me/avatar/confirm",
        json={"object_key": presign_data["object_key"]},
        headers=auth_header(access_token),
    )
    assert confirm.status_code == 200
    assert confirm.json()["avatar_key"] == presign_data["object_key"]
    assert confirm.json()["avatar_url"]

    delete_avatar = await client.delete(
        "/api/v1/users/me/avatar",
        headers=auth_header(access_token),
    )
    assert delete_avatar.status_code == 200
    assert delete_avatar.json()["avatar_key"] is None
