"""Mocked httpx tests for social IntegrationExecutor actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.broker.executor import IntegrationExecutor


@pytest.mark.asyncio
async def test_x_create_post_success():
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"data": {"id": "123", "text": "hi"}}
    response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=response)

    with patch("core.broker.executor.httpx.AsyncClient", return_value=mock_client):
        result = await IntegrationExecutor().execute(
            "x", "token", "create_post", {"text": "hi"}
        )
    assert result["post_id"] == "123"
    assert "x.com" in (result.get("url") or "")


@pytest.mark.asyncio
async def test_x_create_post_error():
    response = MagicMock()
    response.status_code = 403
    response.text = "forbidden"

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=response)

    with patch("core.broker.executor.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="X API error"):
            await IntegrationExecutor().execute(
                "x", "token", "create_post", {"text": "hi"}
            )


@pytest.mark.asyncio
async def test_reddit_submit_success():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "json": {"errors": [], "data": {"id": "abc", "url": "https://reddit.com/r/t"}}
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=response)

    with patch("core.broker.executor.httpx.AsyncClient", return_value=mock_client):
        result = await IntegrationExecutor().execute(
            "reddit",
            "token",
            "submit_post",
            {"subreddit": "test", "title": "T", "text": "Body"},
        )
    assert result["post_id"] == "abc"


@pytest.mark.asyncio
async def test_linkedin_create_post_resolves_author():
    me_response = MagicMock()
    me_response.status_code = 200
    me_response.json.return_value = {"sub": "person123", "name": "Ada"}
    me_response.content = b"{}"

    post_response = MagicMock()
    post_response.status_code = 201
    post_response.json.return_value = {"id": "urn:li:share:9"}
    post_response.content = b'{"id":"urn:li:share:9"}'
    post_response.headers = {}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=me_response)
    mock_client.post = AsyncMock(return_value=post_response)

    with patch("core.broker.executor.httpx.AsyncClient", return_value=mock_client):
        # Nested get_me opens another client; patch covers both.
        result = await IntegrationExecutor().execute(
            "linkedin", "token", "create_post", {"text": "Hello LinkedIn"}
        )
    assert result["post_id"] == "urn:li:share:9"
    assert result["author_urn"] == "urn:li:person:person123"
