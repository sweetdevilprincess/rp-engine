"""Shared test fixtures."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rp_engine.database import Database
from rp_engine.services.card_indexer import CardIndexer
from rp_engine.services.llm_client import LLMResponse


# ---------------------------------------------------------------------------
# Sample markdown content
# ---------------------------------------------------------------------------

SAMPLE_CHARACTER_MD = """---
type: character
name: Dante Moretti
rp: Mafia
is_player_character: false
importance: main
always_load: true
aliases:
  - Beasty
triggers:
  - dante
  - moretti
  - beasty
memories:
  - memory_lilith_wakes_with_dante
initial_trust_score: 16
relationships:
  - name: Lilith
    role: love_interest
    trust: 16
    status: Intimate partner
primary_archetype: POWER_HOLDER
npc_trust_levels:
  Lilith: 16
tags: [mafia, boss, love-interest]
---

Dante is the head of the Moretti crime family.
"""

SAMPLE_MEMORY_MD = """---
type: memory
memory_id: memory_lilith_wakes_with_dante
title: "Lilith Wakes to Find Dante Still Holding Her"
summary: Lilith wakes to discover Dante pushed through the pillow wall
belongs_to: Lilith
rp: Mafia
characters_involved:
  - Lilith
  - Dante
location: "Dante's Penthouse - Guest Room"
when: "Monday, March 17, 2025 - 7:52 AM"
emotional_tone: complex
importance: high
category: discovery
related_memories:
  - memory_dante_says_stay
who_else_remembers:
  Dante:
    perspective: Unconscious action
    memory_ref: null
tags: [vulnerability, trust]
triggers:
  - pillow wall
  - dante holding lilith
---

The memory of waking up to find Dante had crossed the pillow wall barrier.
"""

SAMPLE_SECRET_MD = """---
type: secret
secret_id: secret_lilith_fears_abandonment
title: Lilith is Terrified Dante Will Abandon Her
summary: "Lilith fears Dante will get tired of her"
belongs_to: Lilith
rp: Mafia
category: relationship
known_by:
  - Lilith (herself)
discovery_risk: medium
connects_to_secrets:
  - secret_lilith_felt_safe_with_dante
status: active
tags: [abandonment, fear]
triggers:
  - fear of abandonment
  - gets tired of me
---

Deep-rooted fear that manifests in her behavior.
"""

SAMPLE_LOCATION_MD = """---
type: location
name: Dante's Penthouse
aliases:
  - The Penthouse
  - Dante's place
rp: Mafia
category: building
atmosphere: tense
importance: critical
significant_events:
  - memory_dante_claims_lilith_penthouse
regular_occupants:
  - Dante Moretti (resident)
  - Lilith Graves (guest room)
secrets_hidden_here:
  - secret_lilith_body_chose_dante
connected_locations:
  - file: "The Raven Hotel.md"
    relationship: "nearby"
tags: [penthouse, residence]
triggers:
  - dante's penthouse
  - dante's place
  - guest room
---

The luxurious penthouse apartment.
"""

SAMPLE_PLOT_THREAD_MD = """---
type: plot_thread
thread_id: dante_lilith_tension
name: "Dante-Lilith Core Tension"
rp: Mafia
summary: "The deepening connection between Dante and Lilith"
thread_type: Romance/Conflict
priority: plot_critical
status: active
phase: escalating
related_threads:
  - lilith_misunderstood_by_dante
related_characters:
  - Dante Moretti
  - Lilith Graves
related_locations:
  - Dante's Penthouse
keywords:
  - dante
  - lilith
  - attraction
  - tension
tags: [romance, conflict]
triggers:
  - dante lilith tension
---

The central tension arc of the Mafia RP.
"""

SAMPLE_KNOWLEDGE_MD = """---
type: knowledge
knowledge_id: knowledge_dante_schedule
topic: Dante's Daily Schedule
belongs_to: Lilith
rp: Mafia
related_to:
  - Dante Moretti
importance: medium
tags: [routine, daily]
triggers:
  - dante's schedule
---

Knowledge about Dante's daily routine.
"""

SAMPLE_GUIDELINES_MD = """---
pov_mode: dual
pov_character: ""
dual_characters:
  - Lilith
  - Dante
integrate_user_narrative: true
preserve_user_details: true
narrative_voice: first
tense: present
tone:
  - dark
  - romance
  - slow-burn
  - mafia
scene_pacing: moderate
---
"""


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database with schema applied."""
    database = Database(":memory:")
    await database.initialize()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def db_with_session(db):
    """Database with a pre-created session for exchange tests."""
    from datetime import datetime, timezone

    future = await db.enqueue_write(
        "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
        ["test-session-1", "TestRP", "main", datetime.now(timezone.utc).isoformat()],
    )
    await future
    return db


@pytest_asyncio.fixture
async def ancestry_resolver(db):
    """AncestryResolver backed by the test database."""
    from rp_engine.services.ancestry_resolver import AncestryResolver
    return AncestryResolver(db)


@pytest_asyncio.fixture
async def state_manager(db, ancestry_resolver):
    """StateManager with default trust config and ancestry resolver."""
    from rp_engine.config import TrustConfig
    from rp_engine.services.state_manager import StateManager
    return StateManager(db=db, config=TrustConfig(), resolver=ancestry_resolver)


@pytest_asyncio.fixture
async def branch_manager(db, state_manager, ancestry_resolver):
    """BranchManager backed by the test database."""
    from rp_engine.services.branch_manager import BranchManager
    return BranchManager(db=db, state_manager=state_manager, resolver=ancestry_resolver)


# ---------------------------------------------------------------------------
# Sample card directory fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_card_dir(tmp_path: Path) -> Path:
    """Temp directory structured like an RP vault with sample .md files."""
    rp = tmp_path / "TestRP" / "Story Cards"

    # Characters
    chars = rp / "Characters"
    chars.mkdir(parents=True)
    (chars / "Dante Moretti.md").write_text(SAMPLE_CHARACTER_MD, encoding="utf-8")

    # Memories
    mems = rp / "Memories"
    mems.mkdir(parents=True)
    (mems / "Lilith Wakes to Find Dante Still Holding Her.md").write_text(
        SAMPLE_MEMORY_MD, encoding="utf-8"
    )

    # Secrets
    secrets = rp / "Secrets"
    secrets.mkdir(parents=True)
    (secrets / "Lilith is Terrified Dante Will Abandon Her.md").write_text(
        SAMPLE_SECRET_MD, encoding="utf-8"
    )

    # Locations
    locs = rp / "Locations"
    locs.mkdir(parents=True)
    (locs / "Dante's Penthouse.md").write_text(SAMPLE_LOCATION_MD, encoding="utf-8")

    # Plot Threads
    threads = rp / "Plot Threads"
    threads.mkdir(parents=True)
    (threads / "Dante-Lilith Core Tension.md").write_text(
        SAMPLE_PLOT_THREAD_MD, encoding="utf-8"
    )

    # Knowledge
    knowledge = rp / "Knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "Dante's Daily Schedule.md").write_text(
        SAMPLE_KNOWLEDGE_MD, encoding="utf-8"
    )

    # RP State with guidelines
    state = tmp_path / "TestRP" / "RP State"
    state.mkdir(parents=True)
    (state / "Story_Guidelines.md").write_text(SAMPLE_GUIDELINES_MD, encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Card indexer fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def card_indexer(db, sample_card_dir):
    """CardIndexer with sample data indexed."""
    indexer = CardIndexer(db, sample_card_dir)
    await indexer.full_index("TestRP")
    return indexer


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------

class MockLLMClient:
    """Mock LLM that returns canned NPC reaction JSON. Tracks calls for assertions.

    Routes responses based on model name: analysis model gets analysis JSON,
    everything else gets NPC reaction JSON.
    """

    DEFAULT_REACTION = {
        "character": "Dante Moretti",
        "internalMonologue": "She thinks she can just walk in here.",
        "physicalAction": "His jaw tightens as he sets down his glass.",
        "dialogue": "You've got some nerve showing up unannounced.",
        "emotionalUndercurrent": "controlled irritation",
        "trustShift": {"direction": "neutral", "amount": 0, "reason": None},
    }

    DEFAULT_ANALYSIS = {
        "plotThreads": [],
        "memories": [],
        "knowledgeBoundaries": [],
        "newEntities": {"characters": [], "locations": [], "concepts": []},
        "relationshipDynamics": [],
        "npcInteractions": [],
        "storyState": {
            "characters": {},
            "sceneContext": {"location": None, "timeOfDay": "unknown", "mood": "neutral"},
            "significantEvents": [],
        },
        "sceneSignificance": {
            "score": 1, "categories": [], "brief": None,
            "suggestedCardTypes": [], "inStoryTimestamp": None, "characters": [],
        },
    }

    def __init__(self, reaction_override: dict | None = None, analysis_override: dict | None = None):
        self.calls: list[dict] = []
        self._reaction = reaction_override or self.DEFAULT_REACTION
        self._analysis = analysis_override or self.DEFAULT_ANALYSIS

    class _Models:
        npc_reactions = "mock/npc-model"
        response_analysis = "mock/analysis-model"
        card_generation = "mock/card-model"
        embeddings = "mock/embed-model"

    @property
    def models(self):
        return self._Models()

    async def generate(self, messages, model=None, **kwargs):
        self.calls.append({"messages": messages, "model": model, **kwargs})
        # Route based on model name
        if model and "analysis" in model:
            response_data = self._analysis
        elif model and "card" in model:
            response_data = "# Draft Card\n\nGenerated card content."
        else:
            response_data = self._reaction
        content = response_data if isinstance(response_data, str) else json.dumps(response_data)
        return LLMResponse(
            content=content,
            model=model or "mock-model",
            usage={"total_tokens": 100},
        )

    async def embed(self, texts, model=None):
        import hashlib
        import numpy as np
        results = []
        for text in texts:
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            results.append(rng.randn(384).astype(float).tolist())
        return results

    async def close(self):
        pass


@pytest.fixture
def mock_llm():
    """Mock LLM client with default canned reaction."""
    return MockLLMClient()


# ---------------------------------------------------------------------------
# Test app (no-op lifespan for router tests)
# ---------------------------------------------------------------------------

def create_test_app() -> FastAPI:
    """Create a FastAPI app with all routers but a no-op lifespan.

    Router tests override dependencies for DB/indexer/vault_root.
    This avoids the real lifespan scanning the filesystem.
    """

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    from rp_engine import __version__
    from rp_engine.routers import analyze, branches, cards, context, exchanges, npc, rp, sessions, state, threads, triggers

    test_app = FastAPI(
        title="RP Engine (test)",
        version=__version__,
        lifespan=noop_lifespan,
    )
    test_app.include_router(cards.router)
    test_app.include_router(sessions.router)
    test_app.include_router(exchanges.router)
    test_app.include_router(rp.router)
    test_app.include_router(context.router)
    test_app.include_router(triggers.router)
    test_app.include_router(npc.router)
    test_app.include_router(state.router)
    test_app.include_router(threads.router)
    test_app.include_router(analyze.router)
    test_app.include_router(branches.router)

    # Health endpoint
    from datetime import datetime, timezone

    @test_app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    return test_app
