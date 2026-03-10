"""Shared types for the LLM provider system."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict

    @property
    def prompt_tokens(self) -> int | None:
        return self.usage.get("prompt_tokens")

    @property
    def completion_tokens(self) -> int | None:
        return self.usage.get("completion_tokens")


class LLMError(Exception):
    """Raised when an LLM call fails after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@runtime_checkable
class LLMProvider(Protocol):
    """Interface that all LLM providers must implement."""

    async def generate(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        response_format: dict | None = None,
    ) -> LLMResponse: ...

    async def generate_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.6,
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]: ...

    async def embed(
        self,
        texts: list[str],
        model: str,
    ) -> list[list[float]]: ...

    async def close(self) -> None: ...
