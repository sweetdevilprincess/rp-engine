"""Tests for the LLM client (OpenRouter abstraction)."""

from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio

from rp_engine.config import LLMModelsConfig
from rp_engine.services.llm_client import LLMClient, LLMError, LLMResponse


# ---------------------------------------------------------------------------
# Mock transport for httpx
# ---------------------------------------------------------------------------

class MockTransport(httpx.AsyncBaseTransport):
    """Canned HTTP transport for testing LLMClient without hitting OpenRouter."""

    def __init__(self, responses: list[dict] | None = None):
        self._responses = responses or []
        self._call_idx = 0
        self.requests: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append({
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body,
        })

        if self._call_idx < len(self._responses):
            resp_def = self._responses[self._call_idx]
        else:
            resp_def = self._responses[-1] if self._responses else {}
        self._call_idx += 1

        status = resp_def.get("status", 200)
        headers = resp_def.get("headers", {})
        body_out = resp_def.get("body", {})

        return httpx.Response(
            status_code=status,
            headers=headers,
            json=body_out,
        )


def _make_client(transport: MockTransport) -> LLMClient:
    """Create an LLMClient wired to a mock transport."""
    client = LLMClient(
        api_key="test-key-123",
        models=LLMModelsConfig(),
        fallback_model="test/fallback-model",
    )
    client._client = httpx.AsyncClient(transport=transport)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerate:
    @pytest.mark.asyncio
    async def test_request_body_format(self):
        transport = MockTransport([{
            "body": {
                "choices": [{"message": {"content": "Hello!"}}],
                "model": "test/model",
                "usage": {"total_tokens": 50},
            },
        }])
        client = _make_client(transport)

        result = await client.generate(
            messages=[{"role": "user", "content": "Hi"}],
            model="test/model",
            temperature=0.7,
            max_tokens=500,
        )

        assert len(transport.requests) == 1
        req = transport.requests[0]
        assert req["body"]["model"] == "test/model"
        assert req["body"]["messages"] == [{"role": "user", "content": "Hi"}]
        assert req["body"]["temperature"] == 0.7
        assert req["body"]["max_tokens"] == 500
        await client.close()

    @pytest.mark.asyncio
    async def test_authorization_header(self):
        transport = MockTransport([{
            "body": {
                "choices": [{"message": {"content": "ok"}}],
                "model": "m",
                "usage": {},
            },
        }])
        client = _make_client(transport)

        await client.generate([{"role": "user", "content": "test"}])

        auth = transport.requests[0]["headers"].get("authorization")
        assert auth == "Bearer test-key-123"
        await client.close()

    @pytest.mark.asyncio
    async def test_response_parsing(self):
        transport = MockTransport([{
            "body": {
                "choices": [{"message": {"content": "response text"}}],
                "model": "returned/model",
                "usage": {"total_tokens": 42, "prompt_tokens": 10, "completion_tokens": 32},
            },
        }])
        client = _make_client(transport)

        result = await client.generate([{"role": "user", "content": "hi"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "response text"
        assert result.model == "returned/model"
        assert result.usage["total_tokens"] == 42
        await client.close()

    @pytest.mark.asyncio
    async def test_response_format_passthrough(self):
        transport = MockTransport([{
            "body": {
                "choices": [{"message": {"content": '{"key":"val"}'}}],
                "model": "m",
                "usage": {},
            },
        }])
        client = _make_client(transport)

        await client.generate(
            [{"role": "user", "content": "test"}],
            response_format={"type": "json_object"},
        )

        assert transport.requests[0]["body"]["response_format"] == {"type": "json_object"}
        await client.close()

    @pytest.mark.asyncio
    async def test_fallback_model_used_when_none(self):
        transport = MockTransport([{
            "body": {
                "choices": [{"message": {"content": "ok"}}],
                "model": "test/fallback-model",
                "usage": {},
            },
        }])
        client = _make_client(transport)

        await client.generate([{"role": "user", "content": "test"}])

        assert transport.requests[0]["body"]["model"] == "test/fallback-model"
        await client.close()

    @pytest.mark.asyncio
    async def test_no_choices_raises_error(self):
        transport = MockTransport([{
            "body": {"choices": [], "model": "m", "usage": {}},
        }])
        client = _make_client(transport)

        with pytest.raises(LLMError, match="No choices"):
            await client.generate([{"role": "user", "content": "test"}])
        await client.close()


class TestRetry:
    @pytest.mark.asyncio
    async def test_429_triggers_retry(self):
        transport = MockTransport([
            {
                "status": 429,
                "headers": {"x-ratelimit-reset": "0"},
                "body": {"error": "rate limited"},
            },
            {
                "body": {
                    "choices": [{"message": {"content": "success"}}],
                    "model": "m",
                    "usage": {},
                },
            },
        ])
        client = _make_client(transport)

        result = await client.generate([{"role": "user", "content": "test"}])

        assert result.content == "success"
        assert len(transport.requests) == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_server_error_raises(self):
        transport = MockTransport([{
            "status": 500,
            "body": {"error": "internal server error"},
        }])
        client = _make_client(transport)

        with pytest.raises(LLMError, match="500"):
            await client.generate([{"role": "user", "content": "test"}])
        await client.close()


class TestEmbed:
    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self):
        transport = MockTransport([{
            "body": {
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ],
            },
        }])
        client = _make_client(transport)

        result = await client.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        await client.close()


class TestClose:
    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        transport = MockTransport([])
        client = _make_client(transport)

        await client.close()
        # Verify client is closed (subsequent requests would fail)
        assert client._client.is_closed
