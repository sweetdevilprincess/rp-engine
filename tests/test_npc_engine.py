"""Tests for the NPC engine (reaction pipeline, trimming, parsing)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from rp_engine.config import get_config
from rp_engine.database import Database
from rp_engine.models.npc import NPCReaction, TrustShift
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.npc_engine import NPCEngine
from rp_engine.services.vector_search import VectorSearch
from tests.conftest import MockLLMClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_character(
    db: Database,
    name: str,
    rp_folder: str = "TestRP",
    branch: str = "main",
    importance: str = "main",
    archetype: str = "POWER_HOLDER",
    modifiers: list[str] | None = None,
):
    """Insert a character row for testing."""
    char_id = f"{rp_folder}:{branch}:{name.lower()}"
    future = await db.enqueue_write(
        """INSERT OR REPLACE INTO characters
           (id, rp_folder, branch, name, importance, primary_archetype, behavioral_modifiers, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [char_id, rp_folder, branch, name, importance, archetype,
         json.dumps(modifiers or []), datetime.now(timezone.utc).isoformat()],
    )
    await future


async def _insert_relationship(
    db: Database,
    char_a: str,
    char_b: str,
    rp_folder: str = "TestRP",
    branch: str = "main",
    initial_score: int = 10,
    mod_sum: int = 0,
    dynamic: str = "cautious respect",
):
    """Insert a relationship row for testing."""
    future = await db.enqueue_write(
        """INSERT OR REPLACE INTO relationships
           (rp_folder, branch, character_a, character_b, initial_trust_score,
            trust_modification_sum, dynamic, trust_stage, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [rp_folder, branch, char_a, char_b, initial_score, mod_sum, dynamic,
         "familiar", datetime.now(timezone.utc).isoformat()],
    )
    await future


# ---------------------------------------------------------------------------
# NPC Engine fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def npc_engine(db, mock_llm, card_indexer, sample_card_dir):
    """NPCEngine wired with mock LLM and test DB."""
    from rp_engine.config import SearchConfig
    graph_resolver = GraphResolver(db)
    search_config = SearchConfig()
    vector_search = VectorSearch(db, search_config, embed_fn=mock_llm.embed)
    config = get_config()
    return NPCEngine(
        db=db,
        llm_client=mock_llm,
        graph_resolver=graph_resolver,
        vector_search=vector_search,
        config=config,
        vault_root=sample_card_dir,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetReaction:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, npc_engine, db):
        """Basic pipeline: card exists in DB, reaction returned."""
        await _insert_character(db, "Dante Moretti", archetype="POWER_HOLDER")

        reaction = await npc_engine.get_reaction(
            "Dante Moretti", "Lilith walks in", "Lilith", "TestRP", "main"
        )

        assert isinstance(reaction, NPCReaction)
        assert reaction.character == "Dante Moretti"
        assert reaction.trustShift.direction in ("increase", "decrease", "neutral")

    @pytest.mark.asyncio
    async def test_unknown_npc_raises(self, npc_engine):
        """Requesting reaction for non-existent NPC raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await npc_engine.get_reaction(
                "Nobody", "test scene", "Lilith", "TestRP", "main"
            )

    @pytest.mark.asyncio
    async def test_llm_receives_character_context(self, npc_engine, mock_llm, db):
        """Verify LLM is called with system prompt + character context."""
        await _insert_character(db, "Dante Moretti", archetype="POWER_HOLDER")

        await npc_engine.get_reaction(
            "Dante Moretti", "scene", "Lilith", "TestRP"
        )

        assert len(mock_llm.calls) == 1
        messages = mock_llm.calls[0]["messages"]
        assert messages[0]["role"] == "system"
        assert "NPC Actor Agent" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "Dante" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_trust_data_included(self, npc_engine, mock_llm, db):
        """Trust score and stage should appear in character context."""
        await _insert_character(db, "Dante Moretti")
        await _insert_relationship(db, "Dante Moretti", "Lilith", initial_score=16)

        await npc_engine.get_reaction(
            "Dante Moretti", "scene", "Lilith", "TestRP"
        )

        user_msg = mock_llm.calls[0]["messages"][1]["content"]
        assert "Trust Score: 16" in user_msg
        assert "familiar" in user_msg

    @pytest.mark.asyncio
    async def test_json_mode_requested(self, npc_engine, mock_llm, db):
        """Verify response_format is set for JSON mode."""
        await _insert_character(db, "Dante Moretti")

        await npc_engine.get_reaction(
            "Dante Moretti", "scene", "Lilith", "TestRP"
        )

        assert mock_llm.calls[0]["response_format"] == {"type": "json_object"}


class TestBatchReactions:
    @pytest.mark.asyncio
    async def test_parallel_calls(self, npc_engine, mock_llm, db):
        """Batch should return reactions for each NPC."""
        await _insert_character(db, "Dante Moretti")

        reactions = await npc_engine.get_batch_reactions(
            ["Dante Moretti"], "Lilith enters", "Lilith", "TestRP"
        )

        assert len(reactions) == 1
        assert reactions[0].character == "Dante Moretti"

    @pytest.mark.asyncio
    async def test_batch_tolerates_failures(self, npc_engine, db):
        """Batch should skip failed NPCs and return successful ones."""
        await _insert_character(db, "Dante Moretti")

        # "Nobody" doesn't exist, should fail gracefully
        reactions = await npc_engine.get_batch_reactions(
            ["Dante Moretti", "Nobody"], "scene", "Lilith", "TestRP"
        )

        assert len(reactions) == 1
        assert reactions[0].character == "Dante Moretti"


class TestTrimming:
    def test_archetype_sections_removed(self, npc_engine):
        content = "## Core\nKeep this\n## Dialogue Samples\nRemove this\n## Key\nKeep this too"
        from rp_engine.services.npc_engine import ARCHETYPE_TRIM_SECTIONS
        trimmed = npc_engine._trim_sections(content, ARCHETYPE_TRIM_SECTIONS)
        assert "Keep this" in trimmed
        assert "Remove this" not in trimmed
        assert "Keep this too" in trimmed

    def test_modifier_sections_removed(self, npc_engine):
        content = "## Core\nKeep\n## Setting Applications\nRemove\n## Behavior\nKeep"
        from rp_engine.services.npc_engine import MODIFIER_TRIM_SECTIONS
        trimmed = npc_engine._trim_sections(content, MODIFIER_TRIM_SECTIONS)
        assert "Keep" in trimmed
        assert "Remove" not in trimmed

    def test_intimate_sections_removed_by_default(self, npc_engine):
        content = "## Core\nKeep\n## Intimate/Romantic Behavior\nRemove intimate"
        trimmed = npc_engine._trim_sections(
            content, ["Intimate/Romantic Behavior"], keep_intimate=False
        )
        assert "Keep" in trimmed
        assert "Remove intimate" not in trimmed

    def test_intimate_sections_kept_when_detected(self, npc_engine):
        content = "## Core\nKeep\n## Intimate/Romantic Behavior\nKeep intimate"
        trimmed = npc_engine._trim_sections(content, [], keep_intimate=True)
        assert "Keep intimate" in trimmed

    def test_empty_content(self, npc_engine):
        assert npc_engine._trim_sections("", ["Something"]) == ""

    def test_no_sections_to_remove(self, npc_engine):
        content = "## Core\nKeep everything"
        assert npc_engine._trim_sections(content, []) == content


class TestResponseParsing:
    def test_valid_json(self, npc_engine):
        data = {
            "character": "X",
            "internalMonologue": "thinking",
            "physicalAction": "acting",
            "emotionalUndercurrent": "emotion",
            "trustShift": {"direction": "neutral", "amount": 0},
        }
        reaction = npc_engine._parse_reaction(json.dumps(data), "X")
        assert reaction.character == "X"
        assert reaction.internalMonologue == "thinking"

    def test_markdown_fenced_json(self, npc_engine):
        data = {
            "character": "X",
            "internalMonologue": "t",
            "physicalAction": "a",
            "emotionalUndercurrent": "e",
            "trustShift": {"direction": "neutral", "amount": 0},
        }
        wrapped = f"```json\n{json.dumps(data)}\n```"
        reaction = npc_engine._parse_reaction(wrapped, "X")
        assert reaction.character == "X"

    def test_json_embedded_in_text(self, npc_engine):
        data = {
            "character": "X",
            "internalMonologue": "t",
            "physicalAction": "a",
            "emotionalUndercurrent": "e",
            "trustShift": {"direction": "neutral", "amount": 0},
        }
        text = f"Here is the reaction:\n{json.dumps(data)}\nEnd."
        reaction = npc_engine._parse_reaction(text, "X")
        assert reaction.character == "X"

    def test_fallback_on_garbage(self, npc_engine):
        reaction = npc_engine._parse_reaction("not json at all", "X")
        assert reaction.character == "X"
        assert "Parse error" in reaction.internalMonologue

    def test_empty_content(self, npc_engine):
        reaction = npc_engine._parse_reaction("", "X")
        assert reaction.character == "X"
        assert "Parse error" in reaction.internalMonologue

    def test_json_with_dialogue_null(self, npc_engine):
        data = {
            "character": "Y",
            "internalMonologue": "t",
            "physicalAction": "a",
            "dialogue": None,
            "emotionalUndercurrent": "e",
            "trustShift": {"direction": "increase", "amount": 1, "reason": "helped"},
        }
        reaction = npc_engine._parse_reaction(json.dumps(data), "Y")
        assert reaction.dialogue is None
        assert reaction.trustShift.direction == "increase"
        assert reaction.trustShift.amount == 1


class TestIntimateDetection:
    def test_detects_kiss(self, npc_engine):
        assert npc_engine._detect_intimate("She leaned in for a kiss")

    def test_detects_bedroom(self, npc_engine):
        assert npc_engine._detect_intimate("They went to the bedroom")

    def test_no_false_positive(self, npc_engine):
        assert not npc_engine._detect_intimate("They discussed the business deal")

    def test_empty_string(self, npc_engine):
        assert not npc_engine._detect_intimate("")

    def test_case_insensitive(self, npc_engine):
        assert npc_engine._detect_intimate("He grabbed her WRIST")


class TestTrustStageExtraction:
    def test_extracts_relevant_stage(self, npc_engine):
        """Trust stage section should be extracted when framework is loaded."""
        result = npc_engine._extract_trust_stage_section("hostile", [])
        # Should contain something about hostile behavior
        if npc_engine._trust_framework:
            assert "hostile" in result.lower() or "Hostile" in result

    def test_fallback_when_no_framework(self, npc_engine):
        """If framework is empty, return simple string."""
        old = npc_engine._trust_framework
        npc_engine._trust_framework = ""
        result = npc_engine._extract_trust_stage_section("neutral", [])
        assert "neutral" in result
        npc_engine._trust_framework = old


class TestGetTrust:
    @pytest.mark.asyncio
    async def test_returns_trust_info(self, npc_engine, db):
        await _insert_relationship(db, "Dante Moretti", "Lilith", initial_score=16)

        info = await npc_engine.get_trust("Dante Moretti", "Lilith", "TestRP")

        assert info.npc_name == "Dante Moretti"
        assert info.trust_score == 16
        assert info.trust_stage == "familiar"

    @pytest.mark.asyncio
    async def test_no_relationship_returns_zero(self, npc_engine, db):
        info = await npc_engine.get_trust("Unknown", "Lilith", "TestRP")

        assert info.trust_score == 0
        assert info.trust_stage == "neutral"


class TestListNPCs:
    @pytest.mark.asyncio
    async def test_lists_npcs(self, npc_engine, db):
        """Should list non-player characters from story_cards."""
        npcs = await npc_engine.list_npcs("TestRP")
        # Our sample has Dante Moretti (is_player_character: false)
        names = [n.name for n in npcs]
        assert "Dante Moretti" in names

    @pytest.mark.asyncio
    async def test_excludes_player_characters(self, npc_engine, db):
        """Player characters should be excluded from list."""
        # Insert a player character card
        future = await db.enqueue_write(
            """INSERT INTO story_cards (id, rp_folder, name, card_type, file_path, frontmatter)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ["pc-lilith", "TestRP", "Lilith", "character", "test/lilith.md",
             json.dumps({"is_player_character": True})],
        )
        await future

        npcs = await npc_engine.list_npcs("TestRP")
        names = [n.name for n in npcs]
        assert "Lilith" not in names


class TestNPCSecrets:
    @pytest.mark.asyncio
    async def test_loads_known_secrets(self, npc_engine, db):
        """Secrets with NPC in known_by should be loaded."""
        # Our sample secret has known_by: ["Lilith (herself)"]
        # Insert a secret known by Dante
        future = await db.enqueue_write(
            """INSERT INTO story_cards (id, rp_folder, name, card_type, file_path, content, frontmatter)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ["secret-dante", "TestRP", "Dante's Secret", "secret", "test/secret.md",
             "Dante knows about the money laundering.",
             json.dumps({"known_by": ["Dante Moretti"]})],
        )
        await future

        result = await npc_engine._load_npc_secrets("Dante", "TestRP")
        assert "money laundering" in result

    @pytest.mark.asyncio
    async def test_no_secrets_for_unknown_npc(self, npc_engine, db):
        """NPC not in any known_by should get empty string."""
        result = await npc_engine._load_npc_secrets("Nobody", "TestRP")
        assert result == ""
