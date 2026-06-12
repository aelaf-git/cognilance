"""Integration tests against a running Registry API + PostgreSQL stack."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

BASE_URL = os.getenv("REGISTRY_TEST_URL", "http://127.0.0.1:8088")
API_KEY = os.getenv("TEST_API_KEY", "ck-dev-bootstrap-key")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REGISTRY_TESTS") != "1",
    reason="Set RUN_REGISTRY_TESTS=1 and start `docker compose up` to run integration tests",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def client():
    ac = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
    yield ac
    try:
        await ac.aclose()
    except RuntimeError:
        pass


@pytest.mark.anyio
async def test_health(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_register_discover_heartbeat(client: httpx.AsyncClient):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {
        "name": f"Test Worker {uuid.uuid4().hex[:8]}",
        "url": "http://127.0.0.1:8001",
        "description": "Integration test agent",
        "skills": ["code-review"],
        "tags": ["worker"],
    }
    reg = await client.post("/v1/agents", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    agent = reg.json()
    agent_id = agent["id"]
    assert agent["online"] is True

    discover = await client.get("/v1/agents/discover?skills=code-review&limit=10")
    assert discover.status_code == 200
    agents = discover.json()["agents"]
    assert any(a["id"] == agent_id for a in agents)

    hb = await client.post(f"/v1/agents/{agent_id}/heartbeat", headers=headers)
    assert hb.status_code == 200

    detail = await client.get(f"/v1/agents/{agent_id}")
    assert detail.status_code == 200


@pytest.mark.anyio
async def test_trace_events(client: httpx.AsyncClient):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    event = {
        "trace_id": trace_id,
        "task_id": "task-1",
        "depth": 0,
        "agent_name": "Test Manager",
        "type": "hire_started",
        "text": "Hiring worker",
    }
    response = await client.post("/v1/traces/events", json=event, headers=headers)
    assert response.status_code == 200

    listing = await client.get("/v1/traces?limit=10", headers=headers)
    assert listing.status_code == 200
    traces = listing.json()["traces"]
    assert any(t["trace_id"] == trace_id for t in traces)

    detail = await client.get(f"/v1/traces/{trace_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["events"]) >= 1
