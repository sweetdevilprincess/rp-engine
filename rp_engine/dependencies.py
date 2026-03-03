"""FastAPI dependency injection helpers."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from rp_engine.database import Database
from rp_engine.services.card_indexer import CardIndexer
from rp_engine.services.context_engine import ContextEngine
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.npc_engine import NPCEngine
from rp_engine.services.scene_classifier import SceneClassifier
from rp_engine.services.trigger_evaluator import TriggerEvaluator
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.state_manager import StateManager
from rp_engine.services.vector_search import VectorSearch
from rp_engine.services.thread_tracker import ThreadTracker
from rp_engine.services.timestamp_tracker import TimestampTracker
from rp_engine.services.response_analyzer import ResponseAnalyzer
from rp_engine.services.analysis_pipeline import AnalysisPipeline


def get_db(request: Request) -> Database:
    """Get the database instance from app state."""
    return request.app.state.db


def get_card_indexer(request: Request) -> CardIndexer:
    """Get the card indexer instance from app state."""
    return request.app.state.card_indexer


def get_vault_root(request: Request) -> Path:
    """Get the vault root path from app state."""
    return request.app.state.vault_root


def get_entity_extractor(request: Request) -> EntityExtractor:
    return request.app.state.entity_extractor


def get_scene_classifier(request: Request) -> SceneClassifier:
    return request.app.state.scene_classifier


def get_graph_resolver(request: Request) -> GraphResolver:
    return request.app.state.graph_resolver


def get_vector_search(request: Request) -> VectorSearch:
    return request.app.state.vector_search


def get_trigger_evaluator(request: Request) -> TriggerEvaluator:
    return request.app.state.trigger_evaluator


def get_context_engine(request: Request) -> ContextEngine:
    return request.app.state.context_engine


def get_llm_client(request: Request) -> LLMClient:
    """Get the LLM client instance from app state."""
    return request.app.state.llm_client


def get_npc_engine(request: Request) -> NPCEngine:
    """Get the NPC engine instance from app state."""
    return request.app.state.npc_engine


def get_ancestry_resolver(request: Request) -> AncestryResolver:
    """Get the ancestry resolver instance from app state."""
    return request.app.state.ancestry_resolver


def get_state_manager(request: Request) -> StateManager:
    """Get the state manager instance from app state."""
    return request.app.state.state_manager


def get_thread_tracker(request: Request) -> ThreadTracker:
    """Get the thread tracker instance from app state."""
    return request.app.state.thread_tracker


def get_timestamp_tracker(request: Request) -> TimestampTracker:
    """Get the timestamp tracker instance from app state."""
    return request.app.state.timestamp_tracker


def get_response_analyzer(request: Request) -> ResponseAnalyzer:
    """Get the response analyzer instance from app state."""
    return request.app.state.response_analyzer


def get_analysis_pipeline(request: Request) -> AnalysisPipeline | None:
    """Get the analysis pipeline instance from app state, or None if not initialized."""
    return getattr(request.app.state, "analysis_pipeline", None)


def get_branch_manager(request: Request):
    """Get the branch manager instance from app state."""
    from rp_engine.services.branch_manager import BranchManager
    return request.app.state.branch_manager
