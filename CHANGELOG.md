# Changelog

Auto-generated development log for RP Engine.

## 2026-03-03

### 23:11 - Development changes
- **rp_engine/__main__.py** (write): Created .py file (27 lines)
- **pyproject.toml** (edit): Replaced "[tool.pytest.ini_options]" with "[project.scripts] rp-engine = "rp_engine.__main__:main"  [tool.pytest.ini_options]"


## 2026-03-02

### 02:48 - Development changes
- **rp_engine/mcp_wrapper.py** (write): Created .py file (651 lines)
- **rp_engine/routers/context.py** (edit): Replaced "    _guidelines_cache[rp_folder] = (mtime, resp)     return resp" with "    _guidelines_cache[rp_folder] = (mtime, resp)     return resp   # -------------------------------..."


## 2026-02-28

### 02:45 - Development changes
- **rp_engine/models/context.py** (write): Created .py file (156 lines)
- **rp_engine/models/trigger.py** (write): Created .py file (80 lines)
- **rp_engine/services/entity_extractor.py** (write): Created .py file (313 lines)
- **tests/test_entity_extractor.py** (write): Created .py file (168 lines)
- **rp_engine/services/scene_classifier.py** (write): Created .py file (265 lines)
- **tests/test_scene_classifier.py** (write): Created .py file (151 lines)
- **tests/test_scene_classifier.py** (edit): Replaced "        signals = await classifier.classify(             "They sat together looking at the stars, sm..." with "        signals = await classifier.classify(             "They sat close together, his gaze lingerin..."
- **rp_engine/services/graph_resolver.py** (write): Created .py file (304 lines)
- **tests/test_graph_resolver.py** (write): Created .py file (164 lines)
- **rp_engine/utils/text.py** (write): Created .py file (84 lines)
- **rp_engine/services/vector_search.py** (write): Created .py file (382 lines)
- **tests/test_vector_search.py** (write): Created .py file (233 lines)
- **rp_engine/services/trigger_evaluator.py** (write): Created .py file (468 lines)
- **tests/test_trigger_evaluator.py** (write): Created .py file (345 lines)
- **rp_engine/services/context_engine.py** (write): Created .py file (671 lines)
- **tests/test_context_engine.py** (write): Created .py file (337 lines)
- **rp_engine/routers/context.py** (write): Created .py file (166 lines)
- **rp_engine/routers/triggers.py** (write): Created .py file (194 lines)
- **rp_engine/dependencies.py** (write): Created .py file (56 lines)
- **rp_engine/main.py** (write): Created .py file (126 lines)
- **rp_engine/config.py** (edit): Replaced "class TrustConfig(BaseModel):     increase_value: int = 1     decrease_value: int = 2     session_ma..." with "class TrustConfig(BaseModel):     increase_value: int = 1     decrease_value: int = 2     session_ma..."
- **config.yaml** (write): Created .yaml file (38 lines)
- **tests/conftest.py** (edit): Replaced "    from rp_engine import __version__     from rp_engine.routers import cards, exchanges, guidelines..." with "    from rp_engine import __version__     from rp_engine.routers import cards, context, exchanges, r..."
- **rp_engine/services/trigger_evaluator.py** (edit): Replaced "                # Update last_fired_turn                 await self.db.enqueue_write(               ..." with "                # Update last_fired_turn (await to ensure committed before next eval)               ..."
- **rp_engine/services/context_engine.py** (edit): Replaced "            # Record sent             if session_id:                 now = datetime.now(timezone.utc..." with "            # Record sent (await to ensure committed before next read)             if session_id:   ..."


## 2026-02-27

### 21:29 - Development changes
- **pyproject.toml** (write): Created .toml file (35 lines)
- **.env.example** (write): Created .example file (6 lines)
- **config.yaml** (write): Created .yaml file (36 lines)
- **rp_engine/__init__.py** (write): Created .py file (3 lines)
- **rp_engine/models/__init__.py** (write): Created .py file (1 lines)
- **rp_engine/routers/__init__.py** (write): Created .py file (1 lines)
- **rp_engine/services/__init__.py** (write): Created .py file (1 lines)
- **rp_engine/utils/__init__.py** (write): Created .py file (1 lines)
- **tests/__init__.py** (write): Created .py file (1 lines)
- **rp_engine/config.py** (write): Created .py file (109 lines)
- **rp_engine/migrations/001_initial.sql** (write): Created .sql file (315 lines)
- **rp_engine/database.py** (write): Created .py file (298 lines)
- **rp_engine/main.py** (write): Created .py file (52 lines)
- **tests/conftest.py** (write): Created .py file (15 lines)
- **tests/test_database.py** (write): Created .py file (98 lines)
- **tests/test_health.py** (write): Created .py file (35 lines)
- **pyproject.toml** (edit): Replaced "build-backend = "setuptools.backends._legacy:_Backend"" with "build-backend = "setuptools.build_meta""
- **rp_engine/database.py** (edit): Replaced "    sql: str = field(compare=False)" with "    sql: str = field(compare=False, default="")"
- **rp_engine/database.py** (edit): Replaced "            logger.info("Applying migration: %s", migration_file.name)             sql_content = mig..." with "            logger.info("Applying migration: %s", migration_file.name)             sql_content = mig..."
- **rp_engine/database.py** (edit): Replaced "class Database:" with "def _split_sql(sql: str) -> list[str]:     """Split SQL text into individual statements, respecting ..."
- **rp_engine/database.py** (edit): Replaced "    async def initialize(self) -> None:         """Open connections, run migrations, start write que..." with "    async def initialize(self) -> None:         """Open connections, run migrations, start write que..."
- **tests/test_health.py** (write): Created .py file (49 lines)
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE TABLE sessions (" with "CREATE TABLE IF NOT EXISTS sessions ("
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE TABLE " with "CREATE TABLE IF NOT EXISTS"
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE VIRTUAL TABLE " with "CREATE VIRTUAL TABLE IF NOT EXISTS"
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE TRIGGER " with "CREATE TRIGGER IF NOT EXISTS"
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE INDEX " with "CREATE INDEX IF NOT EXISTS"
- **rp_engine/migrations/001_initial.sql** (edit): Replaced "CREATE TABLE IF NOT EXISTSIF NOT EXISTS sessions (" with "CREATE TABLE IF NOT EXISTS sessions ("
- **rp_engine/migrations/001_initial.sql** (write): Created .sql file (315 lines)


### 22:30 - Development changes
- **rp_engine/utils/frontmatter.py** (write): Created .py file (66 lines)
- **rp_engine/utils/normalization.py** (write): Created .py file (46 lines)
- **rp_engine/models/story_card.py** (write): Created .py file (63 lines)
- **rp_engine/models/session.py** (write): Created .py file (49 lines)
- **rp_engine/models/exchange.py** (write): Created .py file (60 lines)
- **rp_engine/models/rp.py** (write): Created .py file (37 lines)
- **rp_engine/services/card_indexer.py** (write): Created .py file (799 lines)
- **rp_engine/dependencies.py** (write): Created .py file (26 lines)
- **rp_engine/services/file_watcher.py** (write): Created .py file (124 lines)
- **rp_engine/routers/cards.py** (write): Created .py file (251 lines)
- **rp_engine/routers/sessions.py** (write): Created .py file (169 lines)
- **rp_engine/routers/exchanges.py** (write): Created .py file (264 lines)
- **rp_engine/routers/rp.py** (write): Created .py file (135 lines)
- **rp_engine/routers/guidelines.py** (write): Created .py file (56 lines)
- **rp_engine/main.py** (write): Created .py file (94 lines)
- **tests/conftest.py** (write): Created .py file (281 lines)
- **tests/test_frontmatter.py** (write): Created .py file (133 lines)
- **tests/test_normalization.py** (write): Created .py file (62 lines)
- **tests/test_card_indexer.py** (write): Created .py file (227 lines)
- **tests/test_file_watcher.py** (write): Created .py file (45 lines)
- **tests/test_cards_router.py** (write): Created .py file (106 lines)
- **tests/test_sessions_router.py** (write): Created .py file (67 lines)
- **tests/test_exchanges_router.py** (write): Created .py file (157 lines)
- **tests/test_rp_router.py** (write): Created .py file (63 lines)
- **tests/test_guidelines_router.py** (write): Created .py file (47 lines)
- **tests/test_exchange_validation.py** (write): Created .py file (53 lines)
- **tests/conftest.py** (write): Created .py file (331 lines)
- **tests/test_cards_router.py** (write): Created .py file (102 lines)
- **tests/test_sessions_router.py** (write): Created .py file (67 lines)
- **tests/test_exchanges_router.py** (write): Created .py file (157 lines)
- **tests/test_rp_router.py** (write): Created .py file (63 lines)
- **tests/test_guidelines_router.py** (write): Created .py file (45 lines)
- **tests/test_health.py** (write): Created .py file (51 lines)
- **tests/test_sessions_router.py** (write): Created .py file (73 lines)
- **tests/test_exchanges_router.py** (write): Created .py file (164 lines)
- **tests/test_cards_router.py** (write): Created .py file (106 lines)
- **tests/test_rp_router.py** (write): Created .py file (65 lines)
- **tests/test_guidelines_router.py** (write): Created .py file (46 lines)
- **rp_engine/routers/cards.py** (write): Created .py file (247 lines)


### 09:44 - Development changes
- **rp_engine/models/npc.py** (write): Created .py file (65 lines)
- **rp_engine/models/context.py** (edit): Replaced "from rp_engine.models.rp import GuidelinesResponse" with "from rp_engine.models.npc import NPCReaction from rp_engine.models.rp import GuidelinesResponse"
- **rp_engine/models/context.py** (edit): Replaced "    npc_reactions: list = []" with "    npc_reactions: list[NPCReaction] = []"
- **rp_engine/services/llm_client.py** (write): Created .py file (180 lines)
- **rp_engine/services/npc_engine.py** (write): Created .py file (780 lines)
- **rp_engine/routers/npc.py** (write): Created .py file (91 lines)
- **rp_engine/main.py** (edit): Replaced "from rp_engine.services.card_indexer import CardIndexer from rp_engine.services.context_engine impor..." with "from rp_engine.services.card_indexer import CardIndexer from rp_engine.services.context_engine impor..."
- **rp_engine/main.py** (edit): Replaced "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..." with "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..."
- **rp_engine/main.py** (edit): Replaced "    # Shutdown     await file_watcher.stop()     await db.close()" with "    # Shutdown     await llm_client.close()     await file_watcher.stop()     await db.close()"
- **rp_engine/main.py** (edit): Replaced "from rp_engine.routers import cards, context, exchanges, rp, sessions, triggers  # noqa: E402  app.i..." with "from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, triggers  # noqa: E402  ..."
- **rp_engine/dependencies.py** (edit): Replaced "from rp_engine.database import Database from rp_engine.services.card_indexer import CardIndexer from..." with "from rp_engine.database import Database from rp_engine.services.card_indexer import CardIndexer from..."
- **rp_engine/dependencies.py** (edit): Replaced "def get_context_engine(request: Request) -> ContextEngine:     return request.app.state.context_engi..." with "def get_context_engine(request: Request) -> ContextEngine:     return request.app.state.context_engi..."
- **rp_engine/services/context_engine.py** (edit): Replaced "class ContextEngine:     """Orchestrates the full context retrieval pipeline."""      def __init__( ..." with "class ContextEngine:     """Orchestrates the full context retrieval pipeline."""      def __init__( ..."
- **rp_engine/services/context_engine.py** (edit): Replaced "from datetime import datetime, timezone from pathlib import Path" with "from datetime import datetime, timezone from pathlib import Path from typing import Any"
- **rp_engine/services/context_engine.py** (edit): Replaced "        # ---- Stage 5: Assembly ----         warnings = await self._get_warnings(rp_folder, branch)..." with "        # ---- Stage 4b: Background NPC Reactions (Phase 3) ----         npc_reactions = []         ..."
- **tests/conftest.py** (edit): Replaced """"Shared test fixtures."""  from __future__ import annotations  from contextlib import asynccontext..." with """"Shared test fixtures."""  from __future__ import annotations  import json from contextlib import ..."
- **tests/conftest.py** (edit): Replaced "# --------------------------------------------------------------------------- # Test app (no-op life..." with "# --------------------------------------------------------------------------- # Mock LLM client # --..."
- **tests/test_llm_client.py** (write): Created .py file (246 lines)
- **tests/test_npc_engine.py** (write): Created .py file (385 lines)
- **tests/test_npc_router.py** (write): Created .py file (221 lines)


### 18:58 - Development changes
- **rp_engine/models/state.py** (write): Created .py file (126 lines)
- **rp_engine/services/state_manager.py** (write): Created .py file (543 lines)
- **rp_engine/routers/state.py** (write): Created .py file (197 lines)
- **rp_engine/dependencies.py** (edit): Replaced "from rp_engine.services.vector_search import VectorSearch" with "from rp_engine.services.state_manager import StateManager from rp_engine.services.vector_search impo..."
- **rp_engine/dependencies.py** (edit): Replaced "def get_npc_engine(request: Request) -> NPCEngine:     """Get the NPC engine instance from app state..." with "def get_npc_engine(request: Request) -> NPCEngine:     """Get the NPC engine instance from app state..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.services.npc_engine import NPCEngine from rp_engine.services.scene_classifier import ..." with "from rp_engine.services.npc_engine import NPCEngine from rp_engine.services.scene_classifier import ..."
- **rp_engine/main.py** (edit): Replaced "    # Store on app state for dependency injection     app.state.db = db" with "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Sto..."
- **rp_engine/main.py** (edit): Replaced "    app.state.npc_engine = npc_engine      yield" with "    app.state.npc_engine = npc_engine     app.state.state_manager = state_manager      yield"
- **rp_engine/main.py** (edit): Replaced "from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, triggers  # noqa: E402" with "from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, state, triggers  # noqa:..."
- **rp_engine/main.py** (edit): Replaced "app.include_router(npc.router)   @app.get("/health")" with "app.include_router(npc.router) app.include_router(state.router)   @app.get("/health")"


### 19:00 - Development changes
- **tests/test_state_manager.py** (write): Created .py file (492 lines)
- **tests/conftest.py** (edit): Replaced "    from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, triggers" with "    from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, state, triggers"
- **tests/conftest.py** (edit): Replaced "    test_app.include_router(npc.router)      # Health endpoint" with "    test_app.include_router(npc.router)     test_app.include_router(state.router)      # Health endp..."
- **tests/test_state_router.py** (write): Created .py file (235 lines)


### 19:48 - Development changes
- **rp_engine/framework/trust-stages.md** (write): Created .md file (293 lines)


### 20:42 - Development changes
- **rp_engine/models/analysis.py** (write): Created .py file (283 lines)
- **rp_engine/services/thread_tracker.py** (write): Created .py file (320 lines)
- **tests/test_thread_tracker.py** (write): Created .py file (246 lines)
- **rp_engine/services/timestamp_tracker.py** (write): Created .py file (402 lines)
- **tests/test_timestamp_tracker.py** (write): Created .py file (273 lines)
- **rp_engine/services/response_analyzer.py** (write): Created .py file (344 lines)
- **tests/test_response_analyzer.py** (write): Created .py file (305 lines)


### 20:49 - Development changes
- **rp_engine/services/analysis_pipeline.py** (write): Created .py file (289 lines)
- **tests/test_analysis_pipeline.py** (write): Created .py file (356 lines)
- **rp_engine/routers/threads.py** (write): Created .py file (86 lines)
- **rp_engine/routers/analyze.py** (write): Created .py file (45 lines)
- **rp_engine/routers/exchanges.py** (edit): Replaced "from rp_engine.database import Database, PRIORITY_EXCHANGE from rp_engine.dependencies import get_db" with "from rp_engine.database import Database, PRIORITY_EXCHANGE from rp_engine.dependencies import get_an..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "@router.post("", response_model=ExchangeResponse, status_code=201) async def save_exchange(     body..." with "@router.post("", response_model=ExchangeResponse, status_code=201) async def save_exchange(     body..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "    exchange_id = await future      return ExchangeResponse(         id=exchange_id,         exchang..." with "    exchange_id = await future      # Enqueue for async analysis pipeline (Phase 5)     if pipeline ..."
- **rp_engine/routers/cards.py** (edit): Replaced "from rp_engine.database import Database from rp_engine.dependencies import get_card_indexer, get_db,..." with "from rp_engine.database import Database from rp_engine.dependencies import get_card_indexer, get_db,..."
- **rp_engine/routers/cards.py** (edit): Replaced "@router.get("/{card_type}/{name}", response_model=StoryCardDetail)" with "@router.post("/suggest", response_model=dict) async def suggest_card(     body: dict,     db: Databa..."
- **rp_engine/models/session.py** (edit): Replaced "class SessionEndSummary(BaseModel):     significant_events: list[str] = []     trust_changes: list[T..." with "class CharacterStateChange(BaseModel):     character: str     field: str     old_value: str | None =..."
- **rp_engine/routers/sessions.py** (edit): Replaced "from rp_engine.models.session import (     SessionCreate,     SessionEndResponse,     SessionEndSumm..." with "from rp_engine.models.session import (     NewEntity,     PlotThreadStatus,     SceneProgression,   ..."
- **rp_engine/routers/sessions.py** (edit): Replaced "    summary = SessionEndSummary(         significant_events=events,         trust_changes=trust_chan..." with "    rp_folder = row["rp_folder"]     branch = row["branch"]      # New entities from card_gaps     g..."
- **rp_engine/routers/state.py** (edit): Replaced "from rp_engine.dependencies import get_state_manager from rp_engine.models.context import SceneState" with "from rp_engine.dependencies import get_state_manager, get_timestamp_tracker from rp_engine.models.an..."
- **rp_engine/routers/state.py** (edit): Replaced "    return await state_manager.add_event(         event=body.event,         characters=body.characte..." with "    return await state_manager.add_event(         event=body.event,         characters=body.characte..."
- **rp_engine/dependencies.py** (edit): Replaced "from rp_engine.services.state_manager import StateManager from rp_engine.services.vector_search impo..." with "from rp_engine.services.state_manager import StateManager from rp_engine.services.vector_search impo..."
- **rp_engine/dependencies.py** (edit): Replaced "def get_state_manager(request: Request) -> StateManager:     """Get the state manager instance from ..." with "def get_state_manager(request: Request) -> StateManager:     """Get the state manager instance from ..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.services.state_manager import StateManager from rp_engine.services.trigger_evaluator ..." with "from rp_engine.services.analysis_pipeline import AnalysisPipeline from rp_engine.services.response_a..."
- **rp_engine/main.py** (edit): Replaced "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Sto..." with "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Pha..."
- **rp_engine/main.py** (edit): Replaced "    app.state.state_manager = state_manager      yield" with "    app.state.state_manager = state_manager     app.state.thread_tracker = thread_tracker     app.st..."
- **rp_engine/main.py** (edit): Replaced "    # Shutdown     await llm_client.close()     await file_watcher.stop()     await db.close()" with "    # Shutdown     await analysis_pipeline.stop()     await llm_client.close()     await file_watche..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, state, triggers  # noqa:..." with "from rp_engine.routers import analyze, cards, context, exchanges, npc, rp, sessions, state, threads,..."
- **tests/conftest.py** (edit): Replaced "    from rp_engine.routers import cards, context, exchanges, npc, rp, sessions, state, triggers     ..." with "    from rp_engine.routers import analyze, cards, context, exchanges, npc, rp, sessions, state, thre..."
- **tests/conftest.py** (edit): Replaced "class MockLLMClient:     """Mock LLM that returns canned NPC reaction JSON. Tracks calls for asserti..." with "class MockLLMClient:     """Mock LLM that returns canned NPC reaction JSON. Tracks calls for asserti..."
- **tests/conftest.py** (edit): Replaced "    async def generate(self, messages, model=None, **kwargs):         self.calls.append({"messages":..." with "    async def generate(self, messages, model=None, **kwargs):         self.calls.append({"messages":..."
- **tests/test_analysis_pipeline.py** (edit): Replaced "        pipeline = AnalysisPipeline(             db=db,             response_analyzer=response_analy..." with "        pipeline = AnalysisPipeline(             db=db,             response_analyzer=response_analy..."
- **rp_engine/services/thread_tracker.py** (edit): Replaced "            # Write counter             await self.db.enqueue_write(                 """INSERT INTO ..." with "            # Write counter and await so subsequent reads are consistent             future = await ..."


### 20:57 - Development changes
- **tests/test_threads_router.py** (write): Created .py file (122 lines)
- **tests/test_analyze_router.py** (write): Created .py file (75 lines)
- **tests/test_card_suggest.py** (write): Created .py file (133 lines)
- **rp_engine/routers/sessions.py** (edit): Replaced "from fastapi import APIRouter, Depends, HTTPException  from rp_engine.database import Database, PRIO..." with "from pathlib import Path  from fastapi import APIRouter, Depends, HTTPException  from rp_engine.data..."
- **rp_engine/routers/sessions.py** (edit): Replaced "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..." with "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..."
- **rp_engine/routers/sessions.py** (edit): Replaced "    summary = SessionEndSummary(         significant_events=events,         trust_changes=trust_chan..." with "    # Trust writeback: write final trust scores to NPC card frontmatter     await _writeback_trust(d..."
- **tests/test_sessions_router.py** (edit): Replaced """"Tests for sessions router endpoints."""  from __future__ import annotations  import httpx import ..." with """"Tests for sessions router endpoints."""  from __future__ import annotations  from pathlib import ..."
- **tests/test_sessions_router.py** (edit): Replaced "    async def test_end_already_ended(self, app):         async with httpx.AsyncClient(transport=http..." with "    async def test_end_already_ended(self, app):         async with httpx.AsyncClient(transport=http..."


### 23:46 - Development changes
- **rp_engine/migrations/002_branching.sql** (write): Created .sql file (45 lines)
- **rp_engine/models/branch.py** (write): Created .py file (62 lines)
- **rp_engine/services/branch_manager.py** (write): Created .py file (460 lines)
- **rp_engine/services/state_manager.py** (edit): Replaced "from rp_engine.database import PRIORITY_ANALYSIS, Database" with "from rp_engine.database import PRIORITY_ANALYSIS, PRIORITY_EXCHANGE, Database"
- **rp_engine/services/state_manager.py** (edit): Replaced "        if existing:             # Merge: only overwrite fields that are explicitly set             ..." with "        if existing:             # Record state history for rewind support             if exchange_i..."
- **rp_engine/services/state_manager.py** (edit): Replaced "    async def update_scene(         self, updates: SceneUpdate, rp_folder: str, branch: str = "main"..." with "    async def update_scene(         self,         updates: SceneUpdate,         rp_folder: str,     ..."
- **rp_engine/services/state_manager.py** (edit): Replaced "    # ===================================================================     # Events     # =======..." with "    # ===================================================================     # Rewind Support     #..."
- **rp_engine/services/analysis_pipeline.py** (edit): Replaced "            await self.state_manager.update_scene(                 SceneUpdate(                     ..." with "            await self.state_manager.update_scene(                 SceneUpdate(                     ..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "from rp_engine.dependencies import get_analysis_pipeline, get_db from rp_engine.services.analysis_pi..." with "from rp_engine.dependencies import get_analysis_pipeline, get_db, get_state_manager from rp_engine.s..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "async def save_exchange(     body: ExchangeSave,     db: Database = Depends(get_db),     pipeline: A..." with "async def save_exchange(     body: ExchangeSave,     db: Database = Depends(get_db),     pipeline: A..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "        if conflicting:             to_delete = await db.fetch_all(                 "SELECT id FROM ..." with "        if conflicting:             to_delete = await db.fetch_all(                 "SELECT id FROM ..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "@router.delete("/{exchange_id}") async def delete_exchange(     exchange_id: int,     db: Database =..." with "@router.delete("/{exchange_id}") async def delete_exchange(     exchange_id: int,     db: Database =..."
- **rp_engine/routers/branches.py** (write): Created .py file (137 lines)
- **rp_engine/dependencies.py** (edit): Replaced "def get_analysis_pipeline(request: Request) -> AnalysisPipeline | None:     """Get the analysis pipe..." with "def get_analysis_pipeline(request: Request) -> AnalysisPipeline | None:     """Get the analysis pipe..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.services.state_manager import StateManager" with "from rp_engine.services.branch_manager import BranchManager from rp_engine.services.state_manager im..."
- **rp_engine/main.py** (edit): Replaced "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Pha..." with "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Pha..."
- **rp_engine/main.py** (edit): Replaced "    app.state.state_manager = state_manager" with "    app.state.state_manager = state_manager     app.state.branch_manager = branch_manager"
- **rp_engine/main.py** (edit): Replaced "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..." with "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..."
- **rp_engine/main.py** (edit): Replaced "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..." with "    context_engine = ContextEngine(         db=db,         entity_extractor=entity_extractor,       ..."
- **rp_engine/main.py** (edit): Replaced "    # Phase 6: Branch Manager     branch_manager = BranchManager(db=db, state_manager=state_manager)..." with "    # Phase 6: Branch Manager     branch_manager = BranchManager(db=db, state_manager=state_manager)..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.routers import analyze, cards, context, exchanges, npc, rp, sessions, state, threads,..." with "from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, state..."
- **rp_engine/main.py** (edit): Replaced "app.include_router(analyze.router)" with "app.include_router(analyze.router) app.include_router(branches.router)"
- **rp_engine/routers/sessions.py** (edit): Replaced "from fastapi import APIRouter, Depends, HTTPException" with "from fastapi import APIRouter, Depends, HTTPException, Request"
- **rp_engine/routers/sessions.py** (edit): Replaced "@router.post("", response_model=SessionResponse, status_code=201) async def create_session(     body..." with "@router.post("", response_model=SessionResponse, status_code=201) async def create_session(     body..."
- **rp_engine/services/context_engine.py** (edit): Replaced "        self.vault_root = vault_root         self.npc_engine = npc_engine" with "        self.vault_root = vault_root         self.npc_engine = npc_engine         self.branch_manage..."
- **rp_engine/services/context_engine.py** (edit): Replaced "    async def _get_last_response(self, rp_folder: str, branch: str) -> str | None:         """Get th..." with "    async def _get_last_response(self, rp_folder: str, branch: str) -> str | None:         """Get th..."
- **rp_engine/services/context_engine.py** (edit): Replaced "    async def _get_current_exchange(self, rp_folder: str, branch: str) -> int:         """Get the cu..." with "    async def _get_current_exchange(self, rp_folder: str, branch: str) -> int:         """Get the cu..."
- **rp_engine/routers/sessions.py** (edit): Replaced "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..." with "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..."
- **rp_engine/routers/sessions.py** (edit): Replaced "    # Trust writeback: write final trust scores to NPC card frontmatter     await _writeback_trust(d..." with "    # Trust writeback: only for the active branch     branch_manager = getattr(request.app.state, "b..."
- **tests/conftest.py** (edit): Replaced "    from rp_engine.routers import analyze, cards, context, exchanges, npc, rp, sessions, state, thre..." with "    from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, s..."
- **tests/conftest.py** (edit): Replaced "    test_app.include_router(analyze.router)" with "    test_app.include_router(analyze.router)     test_app.include_router(branches.router)"
- **tests/conftest.py** (edit): Replaced "@pytest_asyncio.fixture async def db_with_session(db):     """Database with a pre-created session fo..." with "@pytest_asyncio.fixture async def db_with_session(db):     """Database with a pre-created session fo..."
- **tests/test_branch_manager.py** (write): Created .py file (591 lines)
- **tests/test_branch_manager.py** (edit): Replaced "    @pytest.mark.asyncio     async def test_character_history_recorded(self, db, state_manager, bran..." with "    @pytest.mark.asyncio     async def test_character_history_recorded(self, db, state_manager, bran..."
- **tests/test_exchanges_router.py** (edit): Replaced """"Tests for exchanges router endpoints."""  from __future__ import annotations  import httpx import..." with """"Tests for exchanges router endpoints."""  from __future__ import annotations  import httpx import..."
- **tests/test_sessions_router.py** (edit): Replaced "from rp_engine.dependencies import get_card_indexer, get_db, get_vault_root from rp_engine.utils.fro..." with "from rp_engine.config import TrustConfig from rp_engine.dependencies import get_card_indexer, get_db..."
- **tests/test_sessions_router.py** (edit): Replaced "@pytest.fixture def app(db, vault):     test_app = create_test_app()     test_app.dependency_overrid..." with "@pytest.fixture def app(db, vault):     test_app = create_test_app()     test_app.dependency_overrid..."
- **tests/test_sessions_router.py** (edit): Replaced "        # Create app with overrides         test_app = create_test_app()         test_app.dependency..." with "        # Create app with overrides         test_app = create_test_app()         test_app.dependency..."
- **tests/test_sessions_router.py** (edit): Replaced "        test_app = create_test_app()         test_app.dependency_overrides[get_db] = lambda: db     ..." with "        test_app = create_test_app()         test_app.dependency_overrides[get_db] = lambda: db     ..."


### 02:49 - Development changes
- **tests/test_system_prompt.py** (write): Created .py file (204 lines)
- **README.md** (write): Created .md file (128 lines)
- **docs/client-guide.md** (write): Created .md file (170 lines)


### 02:49 - Development changes
- **tests/test_mcp_wrapper.py** (write): Created .py file (749 lines)
- **docs/system-prompt-guide.md** (write): Created .md file (105 lines)


### 03:44 - Development changes
- **rp_engine/mcp_wrapper.py** (edit): Replaced "if sys.platform == "win32":     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy..." with "if sys.platform == "win32" and sys.version_info < (3, 16):     asyncio.set_event_loop_policy(asyncio..."
- **docs/rp-claude-md-template.md** (write): Created .md file (278 lines)


### 18:55 - Development changes
- **rp_engine/migrations/003_ledger_cow.sql** (write): Created .sql file (174 lines)
- **rp_engine/services/ancestry_resolver.py** (write): Created .py file (343 lines)
- **tests/test_ancestry_resolver.py** (write): Created .py file (423 lines)
- **rp_engine/services/state_manager.py** (write): Created .py file (919 lines)
- **rp_engine/models/state.py** (edit): Replaced "class TrustModification(BaseModel):     date: str | None = None     change: int     direction: str  ..." with "class TrustModification(BaseModel):     date: str | None = None     change: int     direction: str  ..."
- **tests/conftest.py** (edit): Replaced "@pytest_asyncio.fixture async def state_manager(db):     """StateManager with default trust config."..." with "@pytest_asyncio.fixture async def ancestry_resolver(db):     """AncestryResolver backed by the test ..."
- **rp_engine/services/state_manager.py** (edit): Replaced "        # Insert trust modification with new direct columns         future = await self.db.enqueue_w..." with "        # Update session caps         if effective_change > 0:             caps["gained"] += effecti..."
- **rp_engine/services/state_manager.py** (edit): Replaced "    async def _update_legacy_relationship(         self, char_a: str, char_b: str, change: int,     ..." with "    async def _update_legacy_relationship(         self, char_a: str, char_b: str, change: int,     ..."
- **rp_engine/services/branch_manager.py** (write): Created .py file (461 lines)
- **rp_engine/models/branch.py** (edit): Replaced "class CheckpointRestoreResponse(BaseModel):     restored_from: str     exchange_number: int     rewo..." with "class CheckpointRestoreResponse(BaseModel):     restored_from: str     exchange_number: int     new_..."
- **tests/test_branch_manager.py** (write): Created .py file (449 lines)
- **rp_engine/services/state_manager.py** (edit): Replaced "        if not card:             # Fall back to old characters table during migration period        ..." with "        if not card:             # Fall back to old characters table during migration period        ..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "from rp_engine.database import Database, PRIORITY_EXCHANGE from rp_engine.dependencies import get_an..." with "from rp_engine.database import Database, PRIORITY_EXCHANGE from rp_engine.dependencies import get_an..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "@router.post("", response_model=ExchangeResponse, status_code=201) async def save_exchange(     body..." with "@router.post("", response_model=ExchangeResponse, status_code=201) async def save_exchange(     body..."
- **rp_engine/routers/exchanges.py** (edit): Replaced "@router.delete("/{exchange_id}") async def delete_exchange(     exchange_id: int,     db: Database =..." with "@router.delete("/{exchange_id}") async def delete_exchange(     exchange_id: int,     db: Database =..."
- **rp_engine/routers/sessions.py** (edit): Replaced "    # Trust writeback: only for the active branch     branch_manager = getattr(request.app.state, "b..." with "    # Cards are read-only in CoW system — trust lives only in DB.     # No writeback to card files. ..."
- **rp_engine/routers/sessions.py** (edit): Replaced "async def _writeback_trust(     db: Database,     indexer: CardIndexer,     vault_root: Path,     rp..." with ""
- **rp_engine/routers/sessions.py** (edit): Replaced "from rp_engine.database import Database, PRIORITY_EXCHANGE, PRIORITY_ANALYSIS from rp_engine.depende..." with "from rp_engine.database import Database, PRIORITY_EXCHANGE from rp_engine.dependencies import get_db"
- **rp_engine/routers/sessions.py** (edit): Replaced "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..." with "@router.post("/{session_id}/end", response_model=SessionEndResponse) async def end_session(     sess..."
- **rp_engine/routers/sessions.py** (edit): Replaced "from pathlib import Path  from fastapi import APIRouter, Depends, HTTPException, Request" with "from fastapi import APIRouter, Depends, HTTPException, Request"
- **rp_engine/routers/branches.py** (edit): Replaced "@router.post("/{name}/restore", response_model=CheckpointRestoreResponse) async def restore_checkpoi..." with "@router.post("/{name}/restore", response_model=CheckpointRestoreResponse) async def restore_checkpoi..."
- **tests/test_sessions_router.py** (edit): Replaced "class TestTrustWriteback:     async def test_end_session_trust_writeback(self, db, vault):         "..." with "class TestTrustWriteback:     async def test_end_session_cards_read_only(self, db, vault):         "..."
- **tests/test_exchanges_router.py** (edit): Replaced "    async def test_rewind(self, app):         async with httpx.AsyncClient(transport=httpx.ASGITrans..." with "    async def test_rewind(self, app):         """Rewind creates a new branch and saves the exchange ..."
- **rp_engine/main.py** (edit): Replaced "from rp_engine.services.branch_manager import BranchManager from rp_engine.services.state_manager im..." with "from rp_engine.services.ancestry_resolver import AncestryResolver from rp_engine.services.branch_man..."
- **rp_engine/main.py** (edit): Replaced "    # Phase 4: State Manager     state_manager = StateManager(db=db, config=config.trust)      # Pha..." with "    # Ancestry resolver (CoW branching)     resolver = AncestryResolver(db)      # Phase 4: State Ma..."
- **rp_engine/main.py** (edit): Replaced "    app.state.state_manager = state_manager" with "    app.state.ancestry_resolver = resolver     app.state.state_manager = state_manager"
- **rp_engine/dependencies.py** (edit): Replaced "from rp_engine.services.state_manager import StateManager" with "from rp_engine.services.ancestry_resolver import AncestryResolver from rp_engine.services.state_mana..."
- **rp_engine/dependencies.py** (edit): Replaced "def get_state_manager(request: Request) -> StateManager:     """Get the state manager instance from ..." with "def get_ancestry_resolver(request: Request) -> AncestryResolver:     """Get the ancestry resolver in..."
- **rp_engine/migrations/004_data_migration.py** (write): Created .py file (192 lines)
- **rp_engine/migrations/005_drop_old_tables.sql** (write): Created .sql file (18 lines)


### 20:22 - Development changes
- **writing_intelligence/__init__.py** (write): Created .py file (16 lines)
- **rp_engine/models/context.py** (edit): Replaced "class StalenessWarning(BaseModel):     type: str = "stale_analysis"     exchange: int     failed_at:..." with "class StalenessWarning(BaseModel):     type: str = "stale_analysis"     exchange: int     failed_at:..."
- **rp_engine/models/context.py** (edit): Replaced "    card_gaps: list[CardGap] = []     warnings: list[StalenessWarning] = []" with "    card_gaps: list[CardGap] = []     warnings: list[StalenessWarning] = []     writing_constraints:..."
- **writing_intelligence/types.py** (write): Created .py file (174 lines)
- **rp_engine/services/context_engine.py** (edit): Replaced "from rp_engine.models.context import (     CardGap,     CharacterState,     ContextDocument,     Con..." with "from rp_engine.models.context import (     CardGap,     CharacterState,     ContextDocument,     Con..."
- **rp_engine/services/context_engine.py** (edit): Replaced "        self.npc_engine = npc_engine         self.branch_manager = None" with "        self.npc_engine = npc_engine         self.branch_manager = None         self.writing_intelli..."
- **rp_engine/services/context_engine.py** (edit): Replaced "        return None      async def _get_thread_alerts(" with "        return None      async def _get_writing_constraints(         self, user_message: str, last_r..."
- **writing_intelligence/engine.py** (write): Created .py file (163 lines)
- **rp_engine/services/context_engine.py** (edit): Replaced "        (             keyword_cards,             semantic_results,             scene_state,         ..." with "        (             keyword_cards,             semantic_results,             scene_state,         ..."
- **rp_engine/services/context_engine.py** (edit): Replaced "        return ContextResponse(             current_exchange=current_turn,             documents=doc..." with "        return ContextResponse(             current_exchange=current_turn,             documents=doc..."
- **rp_engine/routers/writing.py** (write): Created .py file (87 lines)
- **rp_engine/main.py** (edit): Replaced "    npc_intelligence = NPCIntelligence(db_path=npc_intel_db)      npc_engine = NPCEngine(" with "    npc_intelligence = NPCIntelligence(db_path=npc_intel_db)      # Writing Intelligence     from wr..."
- **rp_engine/main.py** (edit): Replaced "    context_engine.branch_manager = branch_manager      # Phase 5: Analysis Pipeline" with "    context_engine.branch_manager = branch_manager     context_engine.writing_intelligence = writing..."
- **writing_intelligence/db.py** (write): Created .py file (351 lines)
- **rp_engine/main.py** (edit): Replaced "    app.state.npc_intelligence = npc_intelligence     app.state.ancestry_resolver = resolver" with "    app.state.npc_intelligence = npc_intelligence     app.state.writing_intelligence = writing_intel..."
- **rp_engine/main.py** (edit): Replaced "    npc_intelligence.close()     await db.close()" with "    npc_intelligence.close()     writing_intelligence.close()     await db.close()"
- **rp_engine/main.py** (edit): Replaced "from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, state..." with "from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, state..."
- **rp_engine/main.py** (edit): Replaced "app.include_router(branches.router)   @app.get("/health")" with "app.include_router(branches.router) app.include_router(writing.router)   @app.get("/health")"
- **writing_intelligence/classifier.py** (write): Created .py file (143 lines)
- **writing_intelligence/retrieval.py** (write): Created .py file (64 lines)
- **writing_intelligence/injection.py** (write): Created .py file (132 lines)
- **writing_intelligence/feedback.py** (write): Created .py file (256 lines)
- **writing_intelligence/proficiency.py** (write): Created .py file (67 lines)
- **writing_intelligence/_token_utils.py** (write): Created .py file (17 lines)
- **import_writing_data.py** (write): Created .py file (772 lines)
- **writing_intel_cli.py** (write): Created .py file (472 lines)


### 23:12 - Development changes
- **rp_engine/services/card_indexer.py** (edit): Replaced "data["summary"], json.dumps(data["frontmatter"])," with "data["summary"], json.dumps(data["frontmatter"], default=str),"


### 23:14 - Development changes
- **pyproject.toml** (edit): Replaced "include = ["rp_engine*", "npc_intelligence*"]" with "include = ["rp_engine*", "npc_intelligence*", "writing_intelligence*"]"


### 23:24 - Development changes
- **rp_engine/main.py** (edit): Replaced "app = FastAPI(     title="RP Engine",     description="REST API for managing roleplay sessions",    ..." with "app = FastAPI(     title="RP Engine",     description="REST API for managing roleplay sessions",    ..."
- **ui.html** (write): Created .html file (442 lines)


### 23:29 - Development changes
- **.gitignore** (write): Created  file (18 lines)
- **data/.gitkeep** (write): Created  file (1 lines)


### 23:32 - Development changes
- **.gitignore** (edit): Replaced "# Secrets" with "# Dev logs .dev-changes.jsonl  # Secrets"

