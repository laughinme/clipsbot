import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_integration_state"),
]


@pytest.mark.asyncio
async def test_health_endpoints_available(client: AsyncClient):
    health = await client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "operating"

    ping = await client.get("/api/ping")
    assert ping.status_code == 200
    assert ping.json()["status"] == "operating"


@pytest.mark.asyncio
async def test_readiness_endpoint_available(client: AsyncClient):
    ready = await client.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"
    assert ready.json()["checks"]["redis"] == "ok"
    assert ready.json()["checks"]["storage"] == "ok"

