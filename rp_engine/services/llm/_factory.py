"""Provider factory — builds LLM providers from config."""

from __future__ import annotations

import logging
import os

from rp_engine.config import RPEngineConfig
from rp_engine.services.llm._openai_compat import OpenAICompatProvider
from rp_engine.services.llm._openrouter import OpenRouterProvider
from rp_engine.services.llm._types import LLMProvider

logger = logging.getLogger(__name__)


def build_providers(config: RPEngineConfig) -> dict[str, LLMProvider]:
    """Build provider instances from config. Used by container and hot-reload."""
    providers: dict[str, LLMProvider] = {}

    if config.llm.providers:
        for name, pconf in config.llm.providers.items():
            pkey: str | None = pconf.api_key
            if pkey and pkey.startswith("env:"):
                pkey = os.environ.get(pkey[4:], "")

            if pconf.type == "openrouter":
                providers[name] = OpenRouterProvider(
                    api_key=pkey or "",
                    timeout=pconf.timeout,
                    max_concurrency=pconf.max_concurrency,
                )
            elif pconf.type == "openai_compat":
                providers[name] = OpenAICompatProvider(
                    base_url=pconf.base_url or "",
                    api_key=pkey,
                    timeout=pconf.timeout,
                    max_concurrency=pconf.max_concurrency,
                )
            else:
                logger.warning("Unknown provider type '%s' for '%s', skipping", pconf.type, name)
    else:
        # Legacy single-provider mode
        providers["openrouter"] = OpenRouterProvider(api_key=config.effective_api_key())

    return providers
