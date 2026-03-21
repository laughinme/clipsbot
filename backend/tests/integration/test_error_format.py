from datetime import datetime

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_integration_state"),
]


REQUIRED_PROBLEM_KEYS = {
    "type",
    "title",
    "status",
    "detail",
    "error_code",
    "instance",
    "timestamp",
}


def _assert_problem_format(payload: dict, status_code: int) -> None:
    assert REQUIRED_PROBLEM_KEYS.issubset(payload.keys())
    assert payload["status"] == status_code
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_domain_error_response_is_standardized(client: AsyncClient):
    response = await client.get("/api/v1/languages", params={"query": "", "limit": 1})

    assert response.status_code == 400
    payload = response.json()
    _assert_problem_format(payload, 400)
    assert payload["error_code"] == "BAD_REQUEST"
    assert "request_id" in payload
    assert response.headers.get("X-Request-ID") == payload["request_id"]


@pytest.mark.asyncio
async def test_validation_error_response_is_standardized(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
        headers={"X-Client": "mobile"},
    )

    assert response.status_code == 422
    payload = response.json()
    _assert_problem_format(payload, 422)
    assert payload["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert isinstance(payload.get("details"), list)


@pytest.mark.asyncio
async def test_http_error_response_is_standardized(client: AsyncClient):
    response = await client.get("/api/v1/not-found")

    assert response.status_code == 404
    payload = response.json()
    _assert_problem_format(payload, 404)
    assert payload["error_code"] == "HTTP_ERROR"
