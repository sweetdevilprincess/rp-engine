# CLAUDE.md - RP Engine API Development Guide

**Project:** RP Engine - REST API for managing roleplay sessions
**Stack:** Python 3.12+ / FastAPI / SQLite / OpenRouter
**Status:** Active development

---

## What This Is

A pull-based REST API that replaces the hook-based RP management system. The API owns all data and intelligence. Clients send raw text, the API does entity extraction, context retrieval, NPC reactions, state management, and response analysis.

**Core principle:** Smart API, dumb client. The client never parses, extracts entities, or decides what to request.

**Plans and roadmaps:**
- `../.claude/plans/rp-api-overhaul.md` - Master plan (architecture, endpoints, schema, design decisions)
- `../.claude/plans/rp-api-roadmap-foundation.md` - Phases 0-1 (scaffold, data layer)
- `../.claude/plans/rp-api-roadmap-intelligence.md` - Phases 2-3 (context engine, NPC system)
- `../.claude/plans/rp-api-roadmap-state-and-analysis.md` - Phases 4-5 (state, analysis pipeline)
- `../.claude/plans/rp-api-roadmap-advanced.md` - Phases 6-7 (branching, integration, migration)

**Always check the roadmap for the current phase before implementing.** The roadmap is the source of truth for what to build and how.

---

## Project Structure

```
rp-engine/
  CLAUDE.md                 # This file
  pyproject.toml            # Dependencies, metadata, scripts
  .env.example              # Required env vars template
  config.yaml               # Default configuration
  rp_engine/
    __init__.py
    main.py                 # FastAPI app entry point, lifespan
    config.py               # Configuration loading (YAML + env overrides)
    database.py             # SQLite connection, migrations, write queue
    models/                 # Pydantic request/response schemas
      __init__.py
      session.py
      exchange.py
      character.py
      npc.py
      story_card.py
      context.py
      trigger.py
      thread.py
      branch.py
    routers/                # API route handlers (thin - delegate to services)
      __init__.py
      sessions.py
      exchanges.py
      context.py
      npc.py
      state.py
      cards.py
      threads.py
      branches.py
      triggers.py
      search.py
      analyze.py
    services/               # Business logic (where the real work happens)
      __init__.py
      card_indexer.py        # Story card file watcher + indexer
      context_engine.py      # Multi-source context retrieval + assembly
      entity_extractor.py    # Text -> entity matching (no LLM)
      scene_classifier.py    # Heuristic scene signal classification
      trigger_evaluator.py   # Situational trigger condition evaluation
      npc_engine.py          # NPC reactions + trust management
      state_manager.py       # Character/relationship/scene state
      response_analyzer.py   # LLM-based response analysis (post-exchange)
      thread_tracker.py      # Plot thread counter management
      vector_search.py       # Embeddings + hybrid search (vector + BM25)
      graph_resolver.py      # BFS relationship graph traversal
      llm_client.py          # Unified LLM abstraction (OpenRouter)
      file_watcher.py        # Filesystem monitoring for Obsidian edits
    framework/               # NPC archetype/modifier definitions (.md files)
      archetypes/
      modifiers/
    migrations/              # Numbered SQL migration files
      001_initial.sql
    utils/
      __init__.py
      frontmatter.py         # YAML frontmatter parser
      markdown.py            # Markdown processing utilities
      text.py                # Text chunking, cleaning, tokenization
  tests/
    __init__.py
    conftest.py              # Shared fixtures (test DB, sample cards, etc.)
    test_frontmatter.py
    test_graph_resolver.py
    test_trust.py
    test_keyword_matching.py
    test_thread_tracker.py
    test_entity_extractor.py
    test_trigger_evaluator.py
    test_exchanges.py
    test_context.py
    test_npc.py
```

---

## Running the Project

```bash
# From rp-engine/ directory

# Install dependencies
pip install -e ".[dev]"

# Copy env template and add your API key
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY

# Run development server
uvicorn rp_engine.main:app --reload --port 3000

# Run tests
pytest
pytest tests/test_frontmatter.py -v    # Single file
pytest -x                               # Stop on first failure
pytest -k "test_trust"                  # By name pattern

# API docs (auto-generated)
# http://localhost:3000/docs     (Swagger UI)
# http://localhost:3000/redoc    (ReDoc)
```

---

## Architecture Patterns

### Routers Are Thin

Routers validate input (via Pydantic models), call services, return responses. No business logic in routers.

```python
# routers/npc.py - GOOD
@router.post("/react")
async def react(request: NPCReactRequest) -> NPCReaction:
    return await npc_engine.get_reaction(request.npc_name, request.scene_prompt)

# BAD - don't put logic in routers
@router.post("/react")
async def react(request: NPCReactRequest):
    card = await db.fetch("SELECT * FROM story_cards WHERE ...")  # NO
    trust = calculate_trust(...)  # NO
```

### Services Own Business Logic

Each service is a class with async methods. Services get a database connection and other services via dependency injection at startup (not per-request).

```python
# services/npc_engine.py
class NPCEngine:
    def __init__(self, db: Database, llm: LLMClient, graph: GraphResolver):
        self.db = db
        self.llm = llm
        self.graph = graph

    async def get_reaction(self, npc_name: str, scene_prompt: str) -> NPCReaction:
        # Load card, archetype, trust, context, call LLM, return structured result
```

### Write Queue

All database writes go through a single `asyncio.PriorityQueue`. One consumer task processes writes sequentially. Reads bypass the queue entirely (SQLite WAL mode allows concurrent reads).

**Priority order:**
1. Exchange saves (user-facing, must be fast)
2. Analysis state updates
3. File watcher reindexing

Failed writes requeue with exponential backoff.

### Async Background Analysis

`POST /api/exchanges` returns immediately after storing the exchange. Analysis (LLM call to extract state changes) runs as a background task. Analysis tasks are serialized: exchange N completes before N+1 starts.

### File Watcher

`watchfiles` monitors story card `.md` files. On change: re-parse frontmatter, update `story_cards` table, rebuild entity connections/aliases/keywords, invalidate caches. Must handle Obsidian's atomic save pattern (write temp + rename).

---

## Database

### SQLite with WAL Mode

Single file: `data/rp-engine.db`. WAL mode for concurrent reads. The database IS the state store — it replaces 8+ scattered JSON files.

### Migrations

Numbered SQL files in `migrations/`. Applied in order. Tracked in a `_migrations` table. On startup, any unapplied migrations run automatically.

```sql
-- migrations/001_initial.sql
-- Full schema: see rp-api-overhaul.md "Database Schema" section
```

### Key Schema Concepts

- **Every stateful table has `rp_folder` + `branch` columns** for multi-RP and branch isolation
- **State-change tables have `exchange_id` FK** for rewind support (delete exchange -> cascade delete state changes)
- **`story_cards` table caches `.md` file content** — files are source of truth, DB is queryable cache
- **`entity_connections` + `entity_aliases` + `entity_keywords`** enable fast entity lookup without re-parsing files
- **`context_sent` tracks what cards have been sent this session** to prevent redundant injection
- **Trust model is split:** `initial_trust_score` (from card frontmatter) + `trust_modification_sum` (session changes). Live score = sum of both.

### Database Access Pattern

```python
# Reads: direct async queries (bypass write queue)
async def get_character(self, name: str) -> CharacterState:
    row = await self.db.fetch_one("SELECT * FROM characters WHERE name = ?", [name])
    return CharacterState(**row)

# Writes: enqueue through write queue
async def update_character(self, name: str, updates: dict):
    await self.db.enqueue_write(
        priority=2,
        sql="UPDATE characters SET location = ?, emotional_state = ? WHERE name = ?",
        params=[updates["location"], updates["emotional_state"], name]
    )
```

---

## Key API Endpoints

The full endpoint list is in `rp-api-overhaul.md`. Key ones:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/context` | **The main endpoint.** Client sends raw `user_message`, gets back everything: cards, NPC briefs, state, alerts, guidelines. |
| `POST /api/exchanges` | Save a user+assistant exchange. Triggers async analysis. Handles rewinds via `exchange_number`. |
| `POST /api/npc/react` | Get single NPC reaction (LLM call). |
| `POST /api/npc/react-batch` | Batch NPC reactions (shared context, parallel LLM calls). |
| `GET /api/state` | Full state snapshot (characters, relationships, scene, events). |
| `POST /api/sessions` | Start RP session. |
| `POST /api/sessions/{id}/end` | End session (returns accumulated data for LLM to write summaries). |
| `GET /api/cards` | List story cards. |

### POST /api/context Pipeline (5 stages)

1. **Entity Extraction + Scene Classification** - No LLM. Tokenize text, match against known entities, detect active NPCs, classify scene signals.
2. **Retrieval** (parallel) - Keyword match, vector search, state lookup, guidelines, thread alerts, card gaps.
3. **Trigger Evaluation** - Check situational triggers against text + state + scene signals. Fire matching triggers.
4. **Graph Expansion + Context Filtering** - BFS from matched entities. Skip already-sent cards (session tracking).
5. **NPC Handling** - Behavioral briefs for main NPCs (no LLM). Auto-generate reactions for background NPCs only (LLM).
6. **Assembly** - Combine everything into response.

**Target performance:** Stages 1-4: <200ms. With background NPC reactions: <5s.

---

## LLM Integration

All LLM calls go through `services/llm_client.py` which talks to OpenRouter.

```python
class LLMClient:
    async def generate(self, messages, model=None, temperature=0.6, ...) -> LLMResponse
    async def embed(self, texts, model="openai/text-embedding-3-small") -> list[list[float]]
```

**Model routing (configurable per function):**
- NPC reactions: `anthropic/claude-haiku` (default)
- Response analysis: `google/gemini-2.0-flash-001` (default)
- Card generation: `google/gemini-2.0-flash-001` (default)
- Embeddings: `openai/text-embedding-3-small` (default)

**Rate limiting:** Adaptive concurrency via semaphore. Reads OpenRouter rate limit headers after each response. Adjusts concurrency based on remaining headroom. Retries on 429 using `x-ratelimit-reset`.

---

## Configuration

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 3000

paths:
  vault_root: ".."          # Parent directory (Obsidian vault root)
  db_path: "data/rp-engine.db"

llm:
  provider: "openrouter"
  api_key: "env:OPENROUTER_API_KEY"   # Reads from environment
  models:
    npc_reactions: "anthropic/claude-haiku"
    response_analysis: "google/gemini-2.0-flash-001"
    card_generation: "google/gemini-2.0-flash-001"
    embeddings: "openai/text-embedding-3-small"
  fallback_model: "google/gemini-2.0-flash-001"

context:
  max_documents: 5
  max_graph_hops: 2
  stale_threshold_turns: 8   # Re-send card after N turns

search:
  vector_weight: 0.7
  bm25_weight: 0.3
  similarity_threshold: 0.7
  chunk_size: 1000
  chunk_overlap: 200

trust:
  increase_value: 1
  decrease_value: 2
  session_max_gain: 4
  session_max_loss: -10
```

Env vars override config values. `OPENROUTER_API_KEY` is required.

---

## Coding Standards

### Python Style

- Python 3.12+ features are fine (type unions with `|`, match statements, etc.)
- Use `async`/`await` throughout. No sync blocking calls in request handlers.
- Type hints on all function signatures. Pydantic models for all API request/response schemas.
- Use `pathlib.Path` for file paths, not string concatenation.
- Imports: stdlib first, third-party second, local third. Separated by blank lines.

### Pydantic Models

All API request and response bodies get Pydantic models. Defined in `models/`. Use `model_config = ConfigDict(from_attributes=True)` for ORM-like usage.

```python
# models/exchange.py
class ExchangeSave(BaseModel):
    user_message: str
    assistant_response: str
    exchange_number: int | None = None
    idempotency_key: str | None = None
    parent_exchange_number: int | None = None
    session_id: str | None = None
    in_story_timestamp: str | None = None
    metadata: dict | None = None

class ExchangeResponse(BaseModel):
    id: int
    exchange_number: int
    created_at: str
    analysis_status: str = "pending"
    rewound_count: int | None = None
    idempotent_hit: bool | None = None
```

### Error Handling

Use FastAPI's `HTTPException` for API errors. Include `detail` with actionable information.

```python
raise HTTPException(status_code=404, detail=f"NPC '{name}' not found in RP '{rp_folder}'")
raise HTTPException(status_code=409, detail={
    "error": "exchange_conflict",
    "message": f"Expected parent exchange {parent} but latest is {actual}",
    "latest_exchange": actual
})
```

### Testing

- Use `pytest` with `pytest-asyncio` for async tests.
- Test fixtures in `conftest.py`: in-memory SQLite database, sample story cards, mock LLM client.
- Unit tests for pure logic (frontmatter parsing, trust calculation, graph traversal, keyword matching, trigger evaluation).
- Integration tests for service pipelines (exchange save -> analysis -> state update).
- Mock LLM calls in tests. Never hit real API in unit/integration tests.

```python
# conftest.py pattern
@pytest.fixture
async def db():
    """In-memory SQLite database with schema applied."""
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()

@pytest.fixture
def mock_llm():
    """LLM client that returns canned responses."""
    return MockLLMClient(responses={...})
```

### Logging

Use Python's `logging` module. Each service gets its own logger: `logger = logging.getLogger(__name__)`. Log at appropriate levels:
- `DEBUG`: Detailed pipeline steps, cache hits/misses
- `INFO`: Exchange saves, session start/end, analysis completion
- `WARNING`: Stale analysis, fallback behavior, retry
- `ERROR`: LLM call failure, DB write failure, file watcher error

---

## NPC Framework Files

The NPC archetype and modifier definitions live in `rp_engine/framework/`. These are `.md` files copied from `../.claude/agents/npc-agent/framework/`.

**Archetypes** (7): POWER_HOLDER, TRANSACTIONAL, COMMON_PEOPLE, OPPOSITION, SPECIALIST, PROTECTOR, OUTSIDER
**Modifiers** (9): OBSESSIVE, SADISTIC, PARANOID, FANATICAL, NARCISSISTIC, SOCIOPATHIC, ADDICTED, HONOR_BOUND, GRIEF_CONSUMED

Loaded on startup, cached in memory. The NPC engine loads only the relevant archetype + modifiers per character to minimize tokens.

---

## Story Card Frontmatter

Story cards are `.md` files with YAML frontmatter. The frontmatter schema varies by card type. The parser must handle:

- Standard `---` delimiters
- Arrays (both `[a, b]` and `- item` style)
- Nested objects (relationships, knowledge_boundaries, modifier_details)
- All card types: character, NPC, secret, location, plot_thread, memory, knowledge, lore, organization

Templates are in `../z_templates/Story Cards/`. Port from: `../.claude/hooks/modules/shared/context.js` and `../.claude/mcp-servers/npc-agent/frontmatter_index.py`.

---

## Vault Relationship

The API sits inside the Obsidian vault:

```
C:\Users\green\Documents\RP Files\    # Vault root
  Mafia/                                # RP folder
    Story Cards/                        # Card .md files (source of truth)
    RP State/                           # Story_Guidelines.md
  Lilith And Charon/                    # Another RP folder
  rp-engine/                            # THIS PROJECT
    data/rp-engine.db                   # Database
  .claude/                              # Old system (to be removed post-migration)
  z_templates/                          # Card templates
```

The `vault_root` config points to `..` (parent directory). The API watches `{vault_root}/{rp_folder}/Story Cards/**/*.md` for changes.

**Source of truth split:**
- **Markdown files** = source of truth for card *definitions* (content, frontmatter)
- **Database** = source of truth for *runtime state* (character locations, trust scores, exchanges, events)

If the database is deleted, it rebuilds from files on next startup (cards only; runtime state is lost).

---

## Phase Checklist (Quick Reference)

| Phase | Key Deliverable | Status |
|-------|----------------|--------|
| 0 | Running server + database + write queue + `/health` | |
| 1 | Card indexer + file watcher + exchange storage + session management | |
| 2 | `POST /api/context` with entity extraction, graph, vector search, triggers, NPC briefs | |
| 3 | `POST /api/npc/react` with configurable LLM backend | |
| 4 | Centralized state management (characters, relationships, scene, events) | |
| 5 | Async response analysis pipeline + thread tracking + card gaps | |
| 6 | Branch isolation + rewind support + checkpoints | |
| 7 | MCP wrapper + data migration + cleanup + docs | |

**MVP (usable for RP):** Phases 0-3
**Full replacement:** All 7 phases

---

## Porting Reference

Code being ported from the old system:

| New Component | Port From | Key Logic |
|---------------|-----------|-----------|
| `utils/frontmatter.py` | `.claude/hooks/modules/shared/context.js` `parseFrontmatter()` | YAML frontmatter parsing |
| `services/card_indexer.py` | `.claude/mcp-servers/npc-agent/frontmatter_index.py` `build_index()` | Card indexing, entity connections, aliases |
| `services/graph_resolver.py` | `.claude/mcp-servers/npc-agent/frontmatter_index.py` `resolve_context()` | BFS graph traversal |
| `services/npc_engine.py` | `.claude/mcp-servers/npc-agent/server.py` | NPC reaction pipeline, archetype loading |
| `services/vector_search.py` | `rp-agentdb/src/agentdb/vector-store.ts` | Vector store, cosine similarity, BM25, RRF fusion |
| `services/response_analyzer.py` | `.claude/hooks/response-analyzer.js` | LLM extraction schema, state update logic |
| `services/thread_tracker.py` | `.claude/hooks/thread-tracker.js` | Keyword matching, counter logic, thresholds |
| `services/context_engine.py` | `.claude/hooks/semantic-trigger.js` + 6 other hooks | Context assembly pipeline |
| `services/entity_extractor.py` | New (replaces hook-based NPC detection) | Entity + NPC detection from raw text |
| `services/scene_classifier.py` | New | Weighted keyword clusters + state-boosted signals |
| `services/trigger_evaluator.py` | New (replaces TRIGGER_INDEX.md) | Expression DSL, state conditions, signal conditions |

---

## Important Constraints

- **No hooks.** The API replaces all 13 hooks. Don't create hook-based systems.
- **No temp files.** The old system used `.claude/temp/` as a message bus. All state lives in the database or in-memory.
- **Cards stay as markdown.** Story cards are `.md` files edited in Obsidian. The API caches them in SQLite but never deletes or replaces the files as source of truth.
- **Exchange content must be clean.** `assistant_response` in exchanges must contain only RP narrative text. No thinking blocks, tool calls, or meta content. Server-side validation detects and rejects/strips contamination.
- **Trust writeback only at session end.** During sessions, trust changes live in the database only. Card frontmatter is only updated when the session ends. Only the active branch's trust values are written to card files.
- **Analysis is async.** The exchange save endpoint returns immediately. Analysis runs in background. Failures retry with exponential backoff. Serialized: N completes before N+1 starts.
- **Branch isolation is per-table.** Every stateful table has `branch` column. Queries always filter by active branch. Branch creation snapshots state. Exchange numbering is per-branch.
