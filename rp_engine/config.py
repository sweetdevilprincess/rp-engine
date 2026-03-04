"""Configuration loading from config.yaml + environment variable overrides."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 3000
    cors_origins: list[str] = ["http://localhost:*", "http://127.0.0.1:*"]


class PathsConfig(BaseModel):
    vault_root: str = ".."
    db_path: str = "data/rp-engine.db"


class LLMModelsConfig(BaseModel):
    npc_reactions: str = "anthropic/claude-haiku"
    response_analysis: str = "google/gemini-2.0-flash-001"
    card_generation: str = "google/gemini-2.0-flash-001"
    embeddings: str = "openai/text-embedding-3-small"


class LLMConfig(BaseModel):
    provider: str = "openrouter"
    api_key: str = "env:OPENROUTER_API_KEY"
    models: LLMModelsConfig = LLMModelsConfig()
    fallback_model: str = "google/gemini-2.0-flash-001"


class ContextConfig(BaseModel):
    max_documents: int = 5
    max_graph_hops: int = 2
    stale_threshold_turns: int = 8


class SearchConfig(BaseModel):
    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    similarity_threshold: float = 0.7
    chunk_size: int = 1000
    chunk_overlap: int = 200


class TrustConfig(BaseModel):
    increase_value: int = 1
    decrease_value: int = 2
    session_max_gain: int = 8
    session_max_loss: int = -15
    min_score: int = -50
    max_score: int = 50


class RPConfig(BaseModel):
    default_pov_character: str = "Lilith"


class RPEngineConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RP_ENGINE_",
        env_file=(".env", "../.env"),
        env_nested_delimiter="__",
        extra="ignore",
    )

    server: ServerConfig = ServerConfig()
    paths: PathsConfig = PathsConfig()
    llm: LLMConfig = LLMConfig()
    context: ContextConfig = ContextConfig()
    search: SearchConfig = SearchConfig()
    trust: TrustConfig = TrustConfig()
    rp: RPConfig = RPConfig()

    # Standalone field — picks up OPENROUTER_API_KEY env var (no prefix)
    openrouter_api_key: str = ""

    def effective_api_key(self) -> str:
        """Return the best available API key."""
        return self.llm.api_key if self.llm.api_key != "env:OPENROUTER_API_KEY" else self.openrouter_api_key

    def resolve_paths(self) -> None:
        """Resolve vault_root and db_path relative to PROJECT_ROOT."""
        self.paths.vault_root = str((PROJECT_ROOT / self.paths.vault_root).resolve())
        self.paths.db_path = str((PROJECT_ROOT / self.paths.db_path).resolve())


def _load_yaml_defaults() -> dict:
    """Load default config from config.yaml."""
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
            return data if data else {}
    return {}


@lru_cache(maxsize=1)
def get_config() -> RPEngineConfig:
    """Get the singleton configuration instance."""
    yaml_data = _load_yaml_defaults()
    config = RPEngineConfig(**yaml_data)
    config.resolve_paths()
    logger.info("Configuration loaded (vault_root=%s)", config.paths.vault_root)
    return config
