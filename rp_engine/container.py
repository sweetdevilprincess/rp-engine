"""Service container — single object holding all initialized services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rp_engine.database import Database
from rp_engine.services.analysis_pipeline import AnalysisPipeline
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.card_indexer import CardIndexer
from rp_engine.services.context_engine import ContextEngine
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.file_watcher import FileWatcher
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


@dataclass
class ServiceContainer:
    """Holds all service instances. Built once during lifespan startup."""

    db: Database
    card_indexer: CardIndexer
    vault_root: Path
    file_watcher: FileWatcher
    entity_extractor: EntityExtractor
    scene_classifier: SceneClassifier
    graph_resolver: GraphResolver
    vector_search: VectorSearch
    trigger_evaluator: TriggerEvaluator
    context_engine: ContextEngine
    llm_client: LLMClient
    npc_engine: NPCEngine
    npc_intelligence: object  # npc_intelligence.NPCIntelligence (optional dep)
    writing_intelligence: object  # writing_intelligence.WritingIntelligence (optional dep)
    ancestry_resolver: AncestryResolver
    state_manager: StateManager
    branch_manager: BranchManager
    thread_tracker: ThreadTracker
    timestamp_tracker: TimestampTracker
    response_analyzer: ResponseAnalyzer
    analysis_pipeline: AnalysisPipeline
