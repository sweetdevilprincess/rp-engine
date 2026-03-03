"""Tests for the system prompt endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SAMPLE_GUIDELINES_MD, create_test_app
from rp_engine.dependencies import get_db, get_vault_root


class TestSystemPromptEndpoint:
    """Tests for GET /api/context/guidelines/system-prompt."""

    def _make_client(self, tmp_path: Path, db, *, write_guidelines: bool = True):
        """Create a TestClient with dependency overrides."""
        rp_state = tmp_path / "TestRP" / "RP State"
        rp_state.mkdir(parents=True, exist_ok=True)

        if write_guidelines:
            (rp_state / "Story_Guidelines.md").write_text(
                SAMPLE_GUIDELINES_MD, encoding="utf-8"
            )

        app = create_test_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_vault_root] = lambda: tmp_path

        return TestClient(app)

    @pytest.mark.asyncio
    async def test_returns_200_with_content(self, tmp_path: Path, db):
        """System prompt endpoint returns structured prompt."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "system_prompt" in data
        assert "sections" in data
        assert len(data["system_prompt"]) > 100

    @pytest.mark.asyncio
    async def test_sections_contain_npc_framework(self, tmp_path: Path, db):
        """Response sections include the NPC framework."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        data = resp.json()

        npc = data["sections"]["npc_framework"]
        assert "archetypes" in npc
        assert "POWER_HOLDER" in npc["archetypes"]
        assert "OUTSIDER" in npc["archetypes"]
        assert len(npc["archetypes"]) == 7

    @pytest.mark.asyncio
    async def test_sections_contain_modifiers(self, tmp_path: Path, db):
        """NPC framework includes all 9 behavioral modifiers."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        npc = resp.json()["sections"]["npc_framework"]

        assert len(npc["modifiers"]) == 9
        assert "OBSESSIVE" in npc["modifiers"]
        assert "GRIEF_CONSUMED" in npc["modifiers"]

    @pytest.mark.asyncio
    async def test_sections_contain_trust_stages(self, tmp_path: Path, db):
        """NPC framework includes all 8 trust stages with ranges."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        trust = resp.json()["sections"]["npc_framework"]["trust_stages"]

        assert len(trust) == 8
        assert trust["hostile"]["range"] == [-50, -36]
        assert trust["devoted"]["range"] == [35, 50]

    @pytest.mark.asyncio
    async def test_sections_contain_output_format(self, tmp_path: Path, db):
        """Response sections include output format rules."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        output = resp.json()["sections"]["output_format"]

        assert "rules" in output
        assert len(output["rules"]) > 0
        assert any("narrative" in r.lower() for r in output["rules"])

    @pytest.mark.asyncio
    async def test_sections_contain_writing_principles(self, tmp_path: Path, db):
        """Response sections include writing principles."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        writing = resp.json()["sections"]["writing_principles"]

        assert "core_pillars" in writing
        assert len(writing["core_pillars"]) == 5
        assert "emotion_physical_map" in writing
        assert "Fear" in writing["emotion_physical_map"]
        assert "banned_patterns" in writing
        assert "ai_vocabulary" in writing

    @pytest.mark.asyncio
    async def test_rp_guidelines_loaded_from_frontmatter(self, tmp_path: Path, db):
        """RP-specific guidelines are parsed from Story_Guidelines.md."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        rp_guide = resp.json()["sections"]["rp_guidelines"]

        assert rp_guide["pov_mode"] == "dual"
        assert "Lilith" in rp_guide["dual_characters"]
        assert "Dante" in rp_guide["dual_characters"]
        assert rp_guide["narrative_voice"] == "first"
        assert rp_guide["tense"] == "present"
        assert rp_guide["scene_pacing"] == "moderate"

    @pytest.mark.asyncio
    async def test_system_prompt_text_includes_key_sections(self, tmp_path: Path, db):
        """The assembled system_prompt string contains text from all sections."""
        client = self._make_client(tmp_path, db)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        prompt = resp.json()["system_prompt"]

        # Writing section
        assert "Writing Principles" in prompt
        assert "Show Don't Tell" in prompt
        assert "Emotion" in prompt
        assert "Fear" in prompt

        # NPC section
        assert "NPC Framework" in prompt
        assert "POWER_HOLDER" in prompt
        assert "Trust Stages" in prompt

        # Output section
        assert "Output Format" in prompt

        # RP guidelines section
        assert "RP Guidelines" in prompt
        assert "dual" in prompt

    @pytest.mark.asyncio
    async def test_works_without_guidelines_file(self, tmp_path: Path, db):
        """Endpoint succeeds even when Story_Guidelines.md is missing."""
        client = self._make_client(tmp_path, db, write_guidelines=False)

        # Create the RP folder so the path is valid, just no guidelines file
        (tmp_path / "TestRP" / "RP State").mkdir(parents=True, exist_ok=True)

        resp = client.get(
            "/api/context/guidelines/system-prompt",
            params={"rp_folder": "TestRP"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "rp_guidelines" not in data["sections"]
        # Other sections still present
        assert "npc_framework" in data["sections"]
        assert "writing_principles" in data["sections"]
        assert "output_format" in data["sections"]

    @pytest.mark.asyncio
    async def test_missing_rp_folder_returns_422(self, tmp_path: Path, db):
        """Omitting the required rp_folder query param returns 422."""
        client = self._make_client(tmp_path, db)

        resp = client.get("/api/context/guidelines/system-prompt")
        assert resp.status_code == 422
