"""Tests for A2A transport and task models."""

import pytest
from httpx import ASGITransport, AsyncClient

from cognilance.core.models import AgentCard, Skill, Task, TaskState
from cognilance.transport.a2a import A2AClient, A2AServer


@pytest.fixture
def agent_card() -> AgentCard:
    return AgentCard(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        url="http://localhost:8000",
        skills=[Skill.from_name("testing")],
    )


@pytest.fixture
def a2a_server(agent_card: AgentCard) -> A2AServer:
    async def handler(task: Task) -> Task:
        return task.complete(text=f"echo: {task.input.text}")

    return A2AServer(agent_card=agent_card, task_handler=handler)


@pytest.mark.asyncio
async def test_agent_card_endpoint(a2a_server: A2AServer) -> None:
    transport = ASGITransport(app=a2a_server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/a2a")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Agent"
        assert len(data["skills"]) == 1


@pytest.mark.asyncio
async def test_task_lifecycle(a2a_server: A2AServer) -> None:
    transport = ASGITransport(app=a2a_server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/a2a/tasks",
            json={"input": {"text": "hello"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"]["state"] == TaskState.COMPLETED.value
        assert data["output"]["text"] == "echo: hello"


@pytest.mark.asyncio
async def test_a2a_client_send_task(a2a_server: A2AServer) -> None:
    transport = ASGITransport(app=a2a_server.app)
    a2a_client = A2AClient()

    original_post = a2a_client._client.post
    original_get = a2a_client._client.get

    async def patched_post(url: str, **kwargs):  # type: ignore[no-untyped-def]
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            path = url.replace("http://localhost:8000", "")
            return await c.post(path, **kwargs)

    async def patched_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            path = url.replace("http://localhost:8000", "")
            return await c.get(path, **kwargs)

    a2a_client._client.post = patched_post  # type: ignore[method-assign]
    a2a_client._client.get = patched_get  # type: ignore[method-assign]

    result = await a2a_client.send_task("http://localhost:8000", input_text="world")
    assert result.status.state == TaskState.COMPLETED
    assert result.output.text == "echo: world"
    await a2a_client.close()
