"""Backward-compat shim -- all LLM types now live in services.llm package."""

from rp_engine.services.llm import LLMClient, LLMError, LLMResponse  # noqa: F401
