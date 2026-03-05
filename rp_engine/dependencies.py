"""FastAPI dependency injection helpers.

All service lookups go through the ServiceContainer stored on app.state.services.
Individual getters are thin wrappers for use in Depends().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request

from rp_engine.container import ServiceContainer
from rp_engine.database import Database
from rp_engine.services.analysis_pipeline import AnalysisPipeline
from rp_engine.services.auto_save import AutoSaveManager
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.custom_state_manager import CustomStateManager
from rp_engine.services.lance_store import LanceStore
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.card_indexer import CardIndexer
from rp_engine.services.context_engine import ContextEngine
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.npc_engine import NPCEngine
from rp_engine.services.response_analyzer import ResponseAnalyzer
from rp_engine.services.scene_classifier import SceneClassifier
from rp_engine.services.state_manager import StateManager
from rp_engine.services.thread_tracker import ThreadTracker
from rp_engine.services.timestamp_tracker import TimestampTracker
from rp_engine.services.trigger_evaluator import TriggerEvaluator
from rp_engine.services.vector_search import VectorSearch


def _get(request: Request, attr: str) -> Any:
    """Look up a service: prefer container, fall back to direct app.state attr."""
    container = getattr(request.app.state, "services", None)
    if container is not None:
        return getattr(container, attr)
    return getattr(request.app.state, attr)


def get_services(request: Request) -> ServiceContainer:
    """Get the full service container."""
    return request.app.state.services


def get_db(request: Request) -> Database:
    return _get(request, "db")


def get_card_indexer(request: Request) -> CardIndexer:
    return _get(request, "card_indexer")


def get_vault_root(request: Request) -> Path:
    return _get(request, "vault_root")


def get_entity_extractor(request: Request) -> EntityExtractor:
    return _get(request, "entity_extractor")


def get_scene_classifier(request: Request) -> SceneClassifier:
    return _get(request, "scene_classifier")


def get_graph_resolver(request: Request) -> GraphResolver:
    return _get(request, "graph_resolver")


def get_vector_search(request: Request) -> VectorSearch:
    return _get(request, "vector_search")


def get_trigger_evaluator(request: Request) -> TriggerEvaluator:
    return _get(request, "trigger_evaluator")


def get_context_engine(request: Request) -> ContextEngine:
    return _get(request, "context_engine")


def get_llm_client(request: Request) -> LLMClient:
    return _get(request, "llm_client")


def get_npc_engine(request: Request) -> NPCEngine:
    return _get(request, "npc_engine")


def get_ancestry_resolver(request: Request) -> AncestryResolver:
    return _get(request, "ancestry_resolver")


def get_state_manager(request: Request) -> StateManager:
    return _get(request, "state_manager")


def get_thread_tracker(request: Request) -> ThreadTracker:
    return _get(request, "thread_tracker")


def get_timestamp_tracker(request: Request) -> TimestampTracker:
    return _get(request, "timestamp_tracker")


def get_response_analyzer(request: Request) -> ResponseAnalyzer:
    return _get(request, "response_analyzer")


def get_analysis_pipeline(request: Request) -> AnalysisPipeline | None:
    container = getattr(request.app.state, "services", None)
    if container is not None:
        return getattr(container, "analysis_pipeline", None)
    return getattr(request.app.state, "analysis_pipeline", None)


def get_branch_manager(request: Request) -> BranchManager:
    return _get(request, "branch_manager")


def get_auto_save_manager(request: Request) -> AutoSaveManager | None:
    container = getattr(request.app.state, "services", None)
    if container is not None:
        return getattr(container, "auto_save_manager", None)
    return getattr(request.app.state, "auto_save_manager", None)


def get_custom_state_manager(request: Request) -> CustomStateManager:
    return _get(request, "custom_state_manager")


def get_lance_store(request: Request) -> LanceStore:
    return _get(request, "lance_store")


def get_npc_intelligence(request: Request) -> object | None:
    """Get NPC intelligence (optional dependency, typed as object)."""
    container = getattr(request.app.state, "services", None)
    if container is not None:
        return getattr(container, "npc_intelligence", None)
    return getattr(request.app.state, "npc_intelligence", None)


def get_writing_intelligence(request: Request) -> object | None:
    """Get writing intelligence (optional dependency, typed as object)."""
    container = getattr(request.app.state, "services", None)
    if container is not None:
        return getattr(container, "writing_intelligence", None)
    return getattr(request.app.state, "writing_intelligence", None)
