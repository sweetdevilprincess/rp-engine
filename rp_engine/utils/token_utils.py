"""Shared token counting utilities for intelligence packages."""

from collections.abc import Callable


def default_token_counter(text: str) -> int:
    """Fallback: ~1.3 tokens per whitespace-delimited word for English prose."""
    return int(len(text.split()) * 1.3)


def try_tiktoken_counter(model: str = "gpt-4") -> Callable[[str], int] | None:
    """Return a tiktoken-based counter if tiktoken is installed, else None."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        return lambda text: len(enc.encode(text))
    except ImportError:
        return None
