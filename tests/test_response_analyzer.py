"""Tests for the ResponseAnalyzer service."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from rp_engine.database import Database
from rp_engine.models.analysis import AnalysisLLMResult
from rp_engine.services.llm_client import LLMResponse
from rp_engine.services.response_analyzer import ResponseAnalyzer


class AnalysisMockLLM:
    """Mock LLM that returns a canned analysis JSON response."""

    ANALYSIS_RESULT = {
        "plotThreads": [
            {
                "threadName": "Dante-Lilith Tension",
                "status": "developing",
                "development": "Confrontation in warehouse",
                "evidence": "He grabbed her arm",
            }
        ],
        "memories": [
            {
                "description": "Dante confronts Lilith in warehouse",
                "significance": "First physical confrontation",
                "characters": ["Dante Moretti", "Lilith Graves"],
            }
        ],
        "knowledgeBoundaries": [],
        "newEntities": {
            "characters": [],
            "locations": [
                {"name": "The Warehouse", "description": "Old storage", "firstMention": "1"}
            ],
            "concepts": [],
        },
        "relationshipDynamics": [
            {
                "characters": ["Dante Moretti", "Lilith Graves"],
                "changeType": "trust_increase",
                "evidence": "He protected her from falling",
            }
        ],
        "npcInteractions": [
            {
                "npcName": "Dante Moretti",
                "appearedInExchange": [1],
                "actions": ["Grabbed her arm", "Pulled her close"],
                "emotionalState": "protective",
                "trustMoments": [],
                "behaviorNotes": "",
            }
        ],
        "storyState": {
            "characters": {
                "Dante Moretti": {
                    "location": "The Warehouse",
                    "conditions": [],
                    "emotionalState": "tense",
                },
                "Lilith Graves": {
                    "location": "The Warehouse",
                    "conditions": [],
                    "emotionalState": "fearful",
                },
            },
            "sceneContext": {
                "location": "The Warehouse",
                "timeOfDay": "evening",
                "mood": "tense",
            },
            "significantEvents": [
                {
                    "event": "Dante confronts Lilith",
                    "characters": ["Dante Moretti", "Lilith Graves"],
                    "significance": "high",
                }
            ],
        },
        "sceneSignificance": {
            "score": 7,
            "categories": ["relationship_change"],
            "brief": "First physical confrontation between Dante and Lilith.",
            "suggestedCardTypes": ["memory"],
            "inStoryTimestamp": None,
            "characters": ["Dante Moretti", "Lilith Graves"],
        },
    }

    def __init__(self, response_override=None):
        self.calls = []
        self._response = response_override or self.ANALYSIS_RESULT

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
        return LLMResponse(
            content=json.dumps(self._response),
            model=model or "mock-model",
            usage={"total_tokens": 200},
        )


@pytest_asyncio.fixture
async def analyzer(db: Database):
    """ResponseAnalyzer with mock LLM and a test exchange."""
    from datetime import datetime, timezone

    # Create session + exchange
    await db.enqueue_write(
        "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
        ["sess-1", "TestRP", "main", datetime.now(timezone.utc).isoformat()],
    )
    future = await db.enqueue_write(
        """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
           user_message, assistant_response, analysis_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            "sess-1", "TestRP", "main", 1,
            "Lilith walks into the warehouse.",
            "Dante looked up, his jaw tightening. 'You shouldn't be here,' he said.",
            "pending",
            datetime.now(timezone.utc).isoformat(),
        ],
    )
    exchange_id = await future

    mock_llm = AnalysisMockLLM()
    ra = ResponseAnalyzer(db, mock_llm)
    return ra, exchange_id, mock_llm


class TestAnalyze:
    """Test the full analyze method."""

    @pytest.mark.asyncio
    async def test_returns_analysis_result(self, analyzer):
        ra, exchange_id, mock_llm = analyzer
        result = await ra.analyze(
            exchange_id,
            "Lilith walks into the warehouse.",
            "Dante looked up.",
            "TestRP",
        )
        assert isinstance(result, AnalysisLLMResult)
        assert len(result.relationship_dynamics) == 1
        assert result.relationship_dynamics[0].change_type == "trust_increase"

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_model(self, analyzer):
        ra, exchange_id, mock_llm = analyzer
        await ra.analyze(exchange_id, "msg", "resp", "TestRP")
        assert len(mock_llm.calls) == 1
        assert mock_llm.calls[0]["model"] == "mock/analysis-model"

    @pytest.mark.asyncio
    async def test_story_state_extracted(self, analyzer):
        ra, exchange_id, _ = analyzer
        result = await ra.analyze(exchange_id, "msg", "resp", "TestRP")
        assert "Dante Moretti" in result.story_state.characters
        char = result.story_state.characters["Dante Moretti"]
        assert char.location == "The Warehouse"
        assert char.emotional_state == "tense"


class TestNameResolution:
    """Test alias resolution and invalid name filtering."""

    @pytest.mark.asyncio
    async def test_alias_resolved(self, db: Database):
        """Aliases like 'Beasty' should resolve to canonical name."""
        from datetime import datetime, timezone

        # Set up alias
        await db.enqueue_write(
            "INSERT INTO story_cards (id, rp_folder, file_path, card_type, name) VALUES (?, ?, ?, ?, ?)",
            ["TestRP:Dante Moretti", "TestRP", "test.md", "character", "Dante Moretti"],
        )
        await db.enqueue_write(
            "INSERT INTO entity_aliases (alias, entity_id) VALUES (?, ?)",
            ["beasty", "TestRP:Dante Moretti"],
        )
        await db.enqueue_write(
            "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
            ["sess-2", "TestRP", "main", datetime.now(timezone.utc).isoformat()],
        )
        future = await db.enqueue_write(
            """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
               user_message, assistant_response, analysis_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ["sess-2", "TestRP", "main", 1, "msg", "resp", "pending",
             datetime.now(timezone.utc).isoformat()],
        )
        exchange_id = await future

        # LLM returns "Beasty" as character name
        override = dict(AnalysisMockLLM.ANALYSIS_RESULT)
        override["storyState"] = {
            "characters": {
                "Beasty": {"location": "Penthouse", "conditions": [], "emotionalState": "calm"}
            },
            "sceneContext": {"location": "Penthouse", "timeOfDay": "evening", "mood": "calm"},
            "significantEvents": [],
        }

        mock_llm = AnalysisMockLLM(response_override=override)
        ra = ResponseAnalyzer(db, mock_llm)
        result = await ra.analyze(exchange_id, "msg", "resp", "TestRP")
        assert "Dante Moretti" in result.story_state.characters

    def test_invalid_names_filtered(self):
        alias_map = {}
        assert ResponseAnalyzer._resolve_name("Claude", alias_map) is None
        assert ResponseAnalyzer._resolve_name("the man", alias_map) is None
        assert ResponseAnalyzer._resolve_name("Narrator", alias_map) is None
        assert ResponseAnalyzer._resolve_name("", alias_map) is None
        assert ResponseAnalyzer._resolve_name("Dante Moretti", alias_map) == "Dante Moretti"


class TestErrorHandling:
    """Test graceful handling of LLM failures."""

    @pytest.mark.asyncio
    async def test_json_parse_failure(self, db: Database):
        """Invalid JSON from LLM should return empty result."""
        from datetime import datetime, timezone

        await db.enqueue_write(
            "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
            ["sess-3", "TestRP", "main", datetime.now(timezone.utc).isoformat()],
        )
        future = await db.enqueue_write(
            """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
               user_message, assistant_response, analysis_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ["sess-3", "TestRP", "main", 1, "msg", "resp", "pending",
             datetime.now(timezone.utc).isoformat()],
        )
        exchange_id = await future

        class BadLLM:
            class _Models:
                response_analysis = "mock/bad"

            @property
            def models(self):
                return self._Models()

            async def generate(self, **kwargs):
                return LLMResponse(content="not json!", model="bad", usage={})

        ra = ResponseAnalyzer(db, BadLLM())
        result = await ra.analyze(exchange_id, "msg", "resp", "TestRP")
        assert isinstance(result, AnalysisLLMResult)
        assert len(result.relationship_dynamics) == 0

    @pytest.mark.asyncio
    async def test_llm_exception(self, db: Database):
        """LLM raising exception should return empty result."""
        from datetime import datetime, timezone

        await db.enqueue_write(
            "INSERT INTO sessions (id, rp_folder, branch, started_at) VALUES (?, ?, ?, ?)",
            ["sess-4", "TestRP", "main", datetime.now(timezone.utc).isoformat()],
        )
        future = await db.enqueue_write(
            """INSERT INTO exchanges (session_id, rp_folder, branch, exchange_number,
               user_message, assistant_response, analysis_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ["sess-4", "TestRP", "main", 1, "msg", "resp", "pending",
             datetime.now(timezone.utc).isoformat()],
        )
        exchange_id = await future

        class ExplodingLLM:
            class _Models:
                response_analysis = "mock/explode"

            @property
            def models(self):
                return self._Models()

            async def generate(self, **kwargs):
                raise RuntimeError("LLM is on fire")

        ra = ResponseAnalyzer(db, ExplodingLLM())
        result = await ra.analyze(exchange_id, "msg", "resp", "TestRP")
        assert isinstance(result, AnalysisLLMResult)
        assert len(result.plot_threads) == 0
