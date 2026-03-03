"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

from rp_engine import __version__
from rp_engine.config import get_config
from rp_engine.database import Database
from rp_engine.services.card_indexer import CardIndexer
from rp_engine.services.context_engine import ContextEngine
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.file_watcher import FileWatcher
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.npc_engine import NPCEngine
from rp_engine.services.scene_classifier import SceneClassifier
from rp_engine.services.analysis_pipeline import AnalysisPipeline
from rp_engine.services.response_analyzer import ResponseAnalyzer
from rp_engine.services.ancestry_resolver import AncestryResolver
from rp_engine.services.branch_manager import BranchManager
from rp_engine.services.state_manager import StateManager
from rp_engine.services.thread_tracker import ThreadTracker
from rp_engine.services.timestamp_tracker import TimestampTracker
from rp_engine.services.trigger_evaluator import TriggerEvaluator
from rp_engine.services.vector_search import VectorSearch

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    config = get_config()
    vault_root = Path(config.paths.vault_root).resolve()

    # Database
    db = Database(config.paths.db_path)
    await db.initialize()

    # Card indexer
    card_indexer = CardIndexer(db, vault_root)
    rp_folders = card_indexer.get_all_rp_folders()
    for folder in rp_folders:
        result = await card_indexer.full_index(folder)
        logger.info("Indexed %s: %d entities", folder, result["entities"])

    # File watcher
    file_watcher = FileWatcher(card_indexer, vault_root, rp_folders)
    file_watcher.start()

    # Phase 2 services
    entity_extractor = EntityExtractor(db)
    scene_classifier = SceneClassifier(db)
    graph_resolver = GraphResolver(db)
    vector_search = VectorSearch(
        db, config.search, api_key=config.effective_api_key()
    )
    trigger_evaluator = TriggerEvaluator(db)
    context_engine = ContextEngine(
        db=db,
        entity_extractor=entity_extractor,
        scene_classifier=scene_classifier,
        graph_resolver=graph_resolver,
        vector_search=vector_search,
        trigger_evaluator=trigger_evaluator,
        config=config.context,
        vault_root=vault_root,
    )

    # Phase 3: LLM client + NPC engine
    llm_client = LLMClient(
        api_key=config.effective_api_key(),
        models=config.llm.models,
        fallback_model=config.llm.fallback_model,
    )

    # NPC Behavioral Intelligence
    from npc_intelligence import NPCIntelligence
    npc_intel_db = str(Path(config.paths.db_path).parent / "npc_intelligence.db")
    npc_intelligence = NPCIntelligence(db_path=npc_intel_db)

    # Writing Intelligence
    from writing_intelligence import WritingIntelligence
    writing_intel_db = str(Path(config.paths.db_path).parent / "writing_intelligence.db")
    writing_intelligence = WritingIntelligence(db_path=writing_intel_db)

    npc_engine = NPCEngine(
        db=db,
        llm_client=llm_client,
        graph_resolver=graph_resolver,
        vector_search=vector_search,
        config=config,
        vault_root=vault_root,
        npc_intelligence=npc_intelligence,
        scene_classifier=scene_classifier,
    )

    # Ancestry resolver (CoW branching)
    resolver = AncestryResolver(db)

    # Phase 4: State Manager
    state_manager = StateManager(db=db, config=config.trust, resolver=resolver)

    # Phase 6: Branch Manager
    branch_manager = BranchManager(db=db, state_manager=state_manager, resolver=resolver)
    context_engine.branch_manager = branch_manager
    context_engine.writing_intelligence = writing_intelligence

    # Phase 5: Analysis Pipeline
    thread_tracker = ThreadTracker(db)
    timestamp_tracker = TimestampTracker(db, state_manager)
    response_analyzer = ResponseAnalyzer(db, llm_client)
    analysis_pipeline = AnalysisPipeline(
        db=db,
        response_analyzer=response_analyzer,
        state_manager=state_manager,
        thread_tracker=thread_tracker,
        timestamp_tracker=timestamp_tracker,
        trust_config=config.trust,
    )
    analysis_pipeline.start()

    # Store on app state for dependency injection
    app.state.db = db
    app.state.card_indexer = card_indexer
    app.state.vault_root = vault_root
    app.state.file_watcher = file_watcher
    app.state.entity_extractor = entity_extractor
    app.state.scene_classifier = scene_classifier
    app.state.graph_resolver = graph_resolver
    app.state.vector_search = vector_search
    app.state.trigger_evaluator = trigger_evaluator
    app.state.context_engine = context_engine
    app.state.llm_client = llm_client
    app.state.npc_engine = npc_engine
    app.state.npc_intelligence = npc_intelligence
    app.state.writing_intelligence = writing_intelligence
    app.state.ancestry_resolver = resolver
    app.state.state_manager = state_manager
    app.state.branch_manager = branch_manager
    app.state.thread_tracker = thread_tracker
    app.state.timestamp_tracker = timestamp_tracker
    app.state.response_analyzer = response_analyzer
    app.state.analysis_pipeline = analysis_pipeline

    yield

    # Shutdown
    await analysis_pipeline.stop()
    await llm_client.close()
    await file_watcher.stop()
    npc_intelligence.close()
    writing_intelligence.close()
    await db.close()


app = FastAPI(
    title="RP Engine",
    description="REST API for managing roleplay sessions",
    version=__version__,
    lifespan=lifespan,
)

# CORS — allow local HTML files and any localhost origin
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, state, threads, triggers, writing  # noqa: E402

app.include_router(cards.router)
app.include_router(sessions.router)
app.include_router(exchanges.router)
app.include_router(rp.router)
app.include_router(context.router)
app.include_router(triggers.router)
app.include_router(npc.router)
app.include_router(state.router)
app.include_router(threads.router)
app.include_router(analyze.router)
app.include_router(branches.router)
app.include_router(writing.router)


@app.get("/health")
async def health_check():
    config = get_config()
    db = app.state.db if hasattr(app.state, "db") else None
    db_health = await db.health() if db else {"status": "not_initialized"}

    # Add indexed card count
    indexed = None
    if db:
        indexed = await db.fetch_val("SELECT COUNT(*) FROM story_cards")

    return {
        "status": "ok",
        "version": __version__,
        "vault_root": str(config.paths.vault_root),
        "database": db_health,
        "indexed_cards": indexed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
