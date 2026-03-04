"""OpenRouter LLM client abstraction.

Single interface for all LLM calls: chat completions and embeddings.
Uses httpx.AsyncClient with adaptive concurrency and 429 retry.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
from pydantic import BaseModel

from rp_engine.config import LLMModelsConfig

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict


class LLMError(Exception):
    """Raised when an LLM call fails after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LLMClient:
    """Async OpenRouter client with adaptive concurrency and retry."""

    def __init__(
        self,
        api_key: str,
        models: LLMModelsConfig,
        fallback_model: str,
    ) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._api_key = api_key
        self._models = models
        self._fallback = fallback_model
        self._semaphore = asyncio.Semaphore(5)
        self._last_remaining: int | None = None

    @property
    def models(self) -> LLMModelsConfig:
        return self._models

    async def generate(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        model = model or self._fallback

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

        # Extract response
        choices = data.get("choices", [])
        if not choices:
            raise LLMError("No choices in response", status_code=resp.status_code)

        content = choices[0].get("message", {}).get("content", "")
        resp_model = data.get("model", model)
        usage = data.get("usage", {})

        return LLMResponse(content=content, model=resp_model, usage=usage)

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings via OpenRouter."""
        model = model or self._models.embeddings

        body = {
            "model": model,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with self._semaphore:
            resp = await self._request_with_retry(headers, body, url=OPENROUTER_EMBED_URL)

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
        url: str = OPENROUTER_API_URL,
        max_retries: int = 1,
    ) -> httpx.Response:
        """Make a request with one retry on 429."""
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(url, json=body, headers=headers)
            except httpx.TimeoutException as e:
                raise LLMError(f"Request timed out: {e}") from e

            # Track rate limit headers for logging (semaphore stays fixed —
            # replacing a Semaphore object drops any tasks currently waiting on it)
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                try:
                    self._last_remaining = int(remaining)
                except ValueError:
                    pass

            if resp.status_code == 429 and attempt < max_retries:
                # Wait using reset header or default backoff
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

        # Should not reach here, but just in case
        raise LLMError("Max retries exceeded")
