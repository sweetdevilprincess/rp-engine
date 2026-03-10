"""OpenAI-compatible provider for local/third-party LLM servers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx

from rp_engine.services.llm._sse import parse_sse_line
from rp_engine.services.llm._types import LLMError, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    """Provider for any OpenAI-compatible API (Ollama, LM Studio, vLLM, etc.)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        max_concurrency: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._api_key = api_key
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def _build_headers(self) -> dict:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        url = f"{self._base_url}/chat/completions"
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        async with self._semaphore:
            resp = await self._request(body, url)

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMError("No choices in response", status_code=resp.status_code)

        content = choices[0].get("message", {}).get("content", "")
        if not content or not content.strip():
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
        url = f"{self._base_url}/chat/completions"
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self._semaphore, self._client.stream(
            "POST", url, json=body, headers=self._build_headers()
        ) as resp:
            if resp.status_code >= 400:
                error_body = await resp.aread()
                raise LLMError(
                    f"API error {resp.status_code}: {error_body.decode()[:500]}",
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
        """Generate embeddings."""
        url = f"{self._base_url}/embeddings"
        body = {"model": model, "input": texts}

        async with self._semaphore:
            resp = await self._request(body, url)

        data = resp.json()
        embeddings = data.get("data", [])
        return [item["embedding"] for item in sorted(embeddings, key=lambda x: x["index"])]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        body: dict,
        url: str,
        max_retries: int = 1,
    ) -> httpx.Response:
        """Simple retry with standard Retry-After header."""
        headers = self._build_headers()
        for attempt in range(max_retries + 1):
            try:
                resp = await self._client.post(url, json=body, headers=headers)
            except httpx.TimeoutException as e:
                raise LLMError(f"Request timed out: {e}") from e

            if resp.status_code == 429 and attempt < max_retries:
                retry_after = resp.headers.get("Retry-After", "2")
                try:
                    wait = min(float(retry_after), 30.0)
                except ValueError:
                    wait = 2.0
                logger.warning("Rate limited (429), waiting %.1fs", wait)
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                raise LLMError(
                    f"API error {resp.status_code}: {resp.text[:500]}",
                    status_code=resp.status_code,
                )

            return resp

        raise LLMError("Max retries exceeded")
