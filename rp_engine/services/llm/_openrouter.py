"""OpenRouter LLM provider with rate limit handling and retry."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import httpx

from rp_engine.services.llm._sse import parse_sse_line
from rp_engine.services.llm._types import LLMError, LLMResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider:
    """Provider for the OpenRouter API."""

    CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
    EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

    def __init__(
        self,
        api_key: str,
        timeout: float = 30.0,
        max_concurrency: int = 5,
    ) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)
        self._api_key = api_key
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._last_remaining: int | None = None

    async def generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._semaphore:
            resp = await self._request_with_retry(headers, body)

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMError("No choices in response", status_code=resp.status_code)

        content = choices[0].get("message", {}).get("content", "")
        if not content or not content.strip():
            logger.warning("LLM returned empty content for model %s", model)
            raise LLMError("LLM returned empty content", status_code=resp.status_code)

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            usage=data.get("usage", {}),
        )

    async def generate_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.6,
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response, yielding content chunks."""
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._semaphore:  # noqa: SIM117
            async with self._client.stream(
                "POST", self.CHAT_URL, json=body, headers=headers
            ) as resp:
                if resp.status_code >= 400:
                    error_body = await resp.aread()
                    raise LLMError(
                        f"OpenRouter API error {resp.status_code}: {error_body.decode()[:500]}",
                        status_code=resp.status_code,
                    )

                async for line in resp.aiter_lines():
                    content, is_done = parse_sse_line(line)
                    if is_done:
                        break
                    if content:
                        yield content

    async def embed(
        self,
        texts: list[str],
        model: str,
    ) -> list[list[float]]:
        """Generate embeddings via OpenRouter."""
        body = {
            "model": model,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._semaphore:
            resp = await self._request_with_retry(headers, body, url=self.EMBED_URL)

        data = resp.json()
        embeddings = data.get("data", [])
        return [item["embedding"] for item in sorted(embeddings, key=lambda x: x["index"])]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _request_with_retry(
        self,
        headers: dict,
        body: dict,
        url: str = "",
        max_retries: int = 1,
    ) -> httpx.Response:
        """Make a request with one retry on 429."""
        if not url:
            url = self.CHAT_URL

        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(url, json=body, headers=headers)
            except httpx.TimeoutException as e:
                raise LLMError(f"Request timed out: {e}") from e

            # Track rate limit headers
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                try:
                    self._last_remaining = int(remaining)
                except ValueError:
                    pass

            if resp.status_code == 429 and attempt < max_retries:
                reset_at = resp.headers.get("x-ratelimit-reset")
                if reset_at:
                    try:
                        wait_seconds = max(0.5, float(reset_at) - time.time())
                        wait_seconds = min(wait_seconds, 30.0)
                    except (ValueError, TypeError):
                        wait_seconds = 2.0
                else:
                    wait_seconds = 2.0
                logger.warning("Rate limited (429), waiting %.1fs before retry", wait_seconds)
                await asyncio.sleep(wait_seconds)
                continue

            if resp.status_code >= 400:
                detail = resp.text[:500]
                raise LLMError(
                    f"OpenRouter API error {resp.status_code}: {detail}",
                    status_code=resp.status_code,
                )

            return resp

        raise LLMError("Max retries exceeded")
