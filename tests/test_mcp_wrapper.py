"""Tests for the MCP wrapper server.

Mocks httpx to verify that each tool handler sends the correct HTTP method,
URL, query params, and body to the rp-engine API, and that responses are
returned as formatted JSON TextContent.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rp_engine.mcp_wrapper import (
    _json_result,
    _rp_params,
    handle_audit_story_cards,
    handle_batch_npc_reactions,
    handle_check_trust_level,
    handle_create_card,
    handle_end_session,
    handle_get_continuity_brief,
    handle_get_npc_reaction,
    handle_get_scene_context,
    handle_get_state,
    handle_list_existing_cards,
    handle_list_npcs,
    handle_resolve_context,
    handle_save_exchange,
    handle_suggest_card,
    call_tool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with .json() and .raise_for_status()."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _mock_error_response(status_code: int, body: str) -> httpx.HTTPStatusError:
    """Create an httpx.HTTPStatusError for testing error handling."""
    response = MagicMock()
    response.status_code = status_code
    response.text = body
    request = MagicMock()
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=request,
        response=response,
    )


def _patch_client():
    """Return a context manager that patches httpx.AsyncClient.

    Usage::

        with _patch_client() as (mock_client, MockClient):
            mock_client.post.return_value = _mock_response({...})
            result = await handle_something({...})
            mock_client.post.assert_called_once_with(...)
    """
    return _PatchClient()


class _PatchClient:
    """Context manager wrapping httpx.AsyncClient mock setup."""

    def __enter__(self):
        self._patcher = patch("rp_engine.mcp_wrapper.httpx.AsyncClient")
        MockClient = self._patcher.start()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        return mock_client, MockClient

    def __exit__(self, *exc):
        self._patcher.stop()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_rp_params_with_explicit_values(self):
        params = _rp_params({"rp_folder": "Mafia", "branch": "draft"})
        assert params == {"rp_folder": "Mafia", "branch": "draft"}

    def test_rp_params_defaults(self):
        params = _rp_params({})
        # branch defaults to "main", rp_folder depends on env var
        assert params["branch"] == "main"

    def test_rp_params_env_fallback(self, monkeypatch):
        monkeypatch.setenv("RP_FOLDER", "EnvRP")
        params = _rp_params({})
        assert params["rp_folder"] == "EnvRP"
        assert params["branch"] == "main"

    def test_json_result_format(self):
        data = {"foo": "bar", "count": 42}
        result = _json_result(data)
        assert len(result) == 1
        assert result[0].type == "text"
        parsed = json.loads(result[0].text)
        assert parsed == data


# ---------------------------------------------------------------------------
# Tool handler tests
# ---------------------------------------------------------------------------


class TestGetSceneContext:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        with _patch_client() as (mock_client, MockClient):
            mock_client.post.return_value = _mock_response(
                {"current_exchange": 5, "documents": []}
            )

            result = await handle_get_scene_context({
                "user_message": "Lilith enters the bar",
                "rp_folder": "Mafia",
                "branch": "main",
            })

            mock_client.post.assert_called_once_with(
                "/api/context",
                json={"user_message": "Lilith enters the bar"},
                params={"rp_folder": "Mafia", "branch": "main"},
            )
            data = json.loads(result[0].text)
            assert data["current_exchange"] == 5

    @pytest.mark.asyncio
    async def test_includes_last_response(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"current_exchange": 3})

            await handle_get_scene_context({
                "user_message": "She looks around",
                "last_response": "The bar was dimly lit.",
                "rp_folder": "Mafia",
            })

            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"]["last_response"] == "The bar was dimly lit."


class TestSaveExchange:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(
                {"id": 1, "exchange_number": 6, "analysis_status": "pending"}
            )

            result = await handle_save_exchange({
                "user_message": "She nods.",
                "assistant_response": "Dante watches her carefully.",
                "exchange_number": 6,
                "rp_folder": "Mafia",
            })

            mock_client.post.assert_called_once_with(
                "/api/exchanges",
                json={
                    "user_message": "She nods.",
                    "assistant_response": "Dante watches her carefully.",
                    "exchange_number": 6,
                },
                params=None,
            )
            data = json.loads(result[0].text)
            assert data["exchange_number"] == 6

    @pytest.mark.asyncio
    async def test_includes_session_id(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"id": 2, "exchange_number": 1})

            await handle_save_exchange({
                "user_message": "Hi",
                "assistant_response": "Hello",
                "exchange_number": 1,
                "session_id": "sess-abc",
            })

            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"]["session_id"] == "sess-abc"


class TestGetNpcReaction:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        reaction = {
            "character": "Dante Moretti",
            "internalMonologue": "She's testing me.",
            "dialogue": "What do you want?",
            "trustShift": {"direction": "neutral", "amount": 0},
        }
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(reaction)

            result = await handle_get_npc_reaction({
                "npc_name": "Dante Moretti",
                "scene_prompt": "Lilith walks in unexpectedly",
                "rp_folder": "Mafia",
            })

            mock_client.post.assert_called_once_with(
                "/api/npc/react",
                json={
                    "npc_name": "Dante Moretti",
                    "scene_prompt": "Lilith walks in unexpectedly",
                },
                params={"rp_folder": "Mafia", "branch": "main"},
            )
            data = json.loads(result[0].text)
            assert data["character"] == "Dante Moretti"

    @pytest.mark.asyncio
    async def test_includes_pov_character(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"character": "Dante"})

            await handle_get_npc_reaction({
                "npc_name": "Dante",
                "scene_prompt": "Scene",
                "pov_character": "Charon",
                "rp_folder": "TestRP",
            })

            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"]["pov_character"] == "Charon"


class TestBatchNpcReactions:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        reactions = [
            {"character": "Dante", "dialogue": "Hmm."},
            {"character": "Marco", "dialogue": "Boss."},
        ]
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(reactions)

            result = await handle_batch_npc_reactions({
                "npc_names": ["Dante", "Marco"],
                "scene_prompt": "Lilith enters the room",
                "rp_folder": "Mafia",
            })

            mock_client.post.assert_called_once_with(
                "/api/npc/react-batch",
                json={
                    "npc_names": ["Dante", "Marco"],
                    "scene_prompt": "Lilith enters the room",
                },
                params={"rp_folder": "Mafia", "branch": "main"},
            )
            data = json.loads(result[0].text)
            assert len(data) == 2
            assert data[0]["character"] == "Dante"


class TestCheckTrustLevel:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        trust_data = {
            "npc_name": "Dante Moretti",
            "trust_score": 16,
            "trust_stage": "familiar",
        }
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(trust_data)

            result = await handle_check_trust_level({
                "npc_name": "Dante Moretti",
                "rp_folder": "Mafia",
            })

            mock_client.get.assert_called_once_with(
                "/api/npc/Dante Moretti/trust",
                params={"rp_folder": "Mafia", "branch": "main"},
            )
            data = json.loads(result[0].text)
            assert data["trust_score"] == 16

    @pytest.mark.asyncio
    async def test_includes_target_name(self):
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response({"trust_score": 5})

            await handle_check_trust_level({
                "npc_name": "Dante",
                "target_name": "Charon",
                "rp_folder": "TestRP",
            })

            call_args = mock_client.get.call_args
            assert call_args.kwargs["params"]["target_name"] == "Charon"


class TestListNpcs:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        npcs = [
            {"name": "Dante Moretti", "primary_archetype": "POWER_HOLDER"},
            {"name": "Marco", "primary_archetype": "PROTECTOR"},
        ]
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(npcs)

            result = await handle_list_npcs({"rp_folder": "Mafia"})

            mock_client.get.assert_called_once_with(
                "/api/npcs",
                params={"rp_folder": "Mafia", "branch": "main"},
            )
            data = json.loads(result[0].text)
            assert len(data) == 2


class TestGetState:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        state = {
            "characters": [{"name": "Lilith", "location": "Bar"}],
            "relationships": [],
            "scene": {"location": "The Dive Bar"},
        }
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(state)

            result = await handle_get_state({"rp_folder": "Mafia", "branch": "draft"})

            mock_client.get.assert_called_once_with(
                "/api/state",
                params={"rp_folder": "Mafia", "branch": "draft"},
            )
            data = json.loads(result[0].text)
            assert data["scene"]["location"] == "The Dive Bar"


class TestGetContinuityBrief:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        brief = {"active_tensions": [], "plot_threads": []}
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(brief)

            result = await handle_get_continuity_brief({
                "scene_summary": "Lilith at the penthouse",
                "focus_areas": ["plot_threads", "secrets"],
                "rp_folder": "Mafia",
            })

            call_args = mock_client.get.call_args
            assert call_args.args[0] == "/api/context/continuity"
            params = call_args.kwargs["params"]
            assert params["scene_summary"] == "Lilith at the penthouse"
            assert params["focus_areas"] == "plot_threads,secrets"
            assert params["rp_folder"] == "Mafia"

    @pytest.mark.asyncio
    async def test_minimal_params(self):
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response({})

            await handle_get_continuity_brief({})

            call_args = mock_client.get.call_args
            params = call_args.kwargs["params"]
            assert "scene_summary" not in params
            assert "focus_areas" not in params


class TestResolveContext:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        resolved = {"entities": [{"name": "Dante", "connections": []}]}
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(resolved)

            result = await handle_resolve_context({
                "keywords": ["Dante", "penthouse"],
                "scene_description": "Dante is pacing in the penthouse",
                "max_hops": 3,
                "max_results": 10,
                "rp_folder": "Mafia",
            })

            mock_client.post.assert_called_once_with(
                "/api/context/resolve",
                json={
                    "keywords": ["Dante", "penthouse"],
                    "scene_description": "Dante is pacing in the penthouse",
                    "max_hops": 3,
                    "max_results": 10,
                },
                params={"rp_folder": "Mafia"},
            )
            data = json.loads(result[0].text)
            assert data["entities"][0]["name"] == "Dante"

    @pytest.mark.asyncio
    async def test_minimal_params(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"entities": []})

            await handle_resolve_context({"keywords": ["test"]})

            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"] == {"keywords": ["test"]}
            # No rp_folder in params when not specified and no env var
            # (params may be empty or have rp_folder from env)


class TestAuditStoryCards:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        audit = {"gaps": [{"entity": "Marco", "type": "npc"}]}
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(audit)

            result = await handle_audit_story_cards({
                "rp_folder": "Mafia",
                "mode": "deep",
                "session_id": "sess-1",
            })

            mock_client.post.assert_called_once_with(
                "/api/cards/audit",
                json={
                    "rp_folder": "Mafia",
                    "mode": "deep",
                    "session_id": "sess-1",
                },
                params=None,
            )
            data = json.loads(result[0].text)
            assert data["gaps"][0]["entity"] == "Marco"

    @pytest.mark.asyncio
    async def test_empty_params(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"gaps": []})

            await handle_audit_story_cards({})

            call_args = mock_client.post.call_args
            # Body should not have rp_folder if not set and no env var
            body = call_args.kwargs["json"]
            # mode and session_id should be absent
            assert "mode" not in body
            assert "session_id" not in body


class TestSuggestCard:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        suggestion = {"entity_name": "Marco", "card_type": "npc", "content": "# Marco\n..."}
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(suggestion)

            result = await handle_suggest_card({
                "entity_name": "Marco",
                "card_type": "npc",
                "rp_folder": "Mafia",
                "additional_context": "Dante's right-hand man",
            })

            mock_client.post.assert_called_once_with(
                "/api/cards/suggest",
                json={
                    "entity_name": "Marco",
                    "card_type": "npc",
                    "rp_folder": "Mafia",
                    "additional_context": "Dante's right-hand man",
                },
                params=None,
            )
            data = json.loads(result[0].text)
            assert data["entity_name"] == "Marco"


class TestListExistingCards:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        cards = [{"name": "Dante Moretti", "type": "character"}]
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(cards)

            result = await handle_list_existing_cards({
                "card_type": "character",
                "rp_folder": "Mafia",
            })

            mock_client.get.assert_called_once_with(
                "/api/cards",
                params={"card_type": "character", "rp_folder": "Mafia"},
            )
            data = json.loads(result[0].text)
            assert len(data) == 1

    @pytest.mark.asyncio
    async def test_no_filters(self):
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response([])

            await handle_list_existing_cards({})

            call_args = mock_client.get.call_args
            params = call_args.kwargs["params"]
            assert "card_type" not in params


class TestEndSession:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        session_data = {
            "session_id": "sess-abc",
            "significant_events": ["Dante kissed Lilith"],
            "trust_changes": [{"npc": "Dante", "delta": 2}],
        }
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(session_data)

            result = await handle_end_session({"session_id": "sess-abc"})

            mock_client.post.assert_called_once_with(
                "/api/sessions/sess-abc/end",
                json={},
                params=None,
            )
            data = json.loads(result[0].text)
            assert data["session_id"] == "sess-abc"
            assert len(data["significant_events"]) == 1


class TestCreateCard:
    @pytest.mark.asyncio
    async def test_sends_correct_request(self):
        created = {"name": "Morning at Penthouse", "type": "memory", "path": "Mafia/Story Cards/Memories/Morning at Penthouse.md"}
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response(created)

            result = await handle_create_card({
                "card_type": "memory",
                "name": "Morning at Penthouse",
                "content": "Lilith woke up to find Dante still holding her.",
                "frontmatter": {"belongs_to": "Lilith", "importance": "high"},
                "rp_folder": "Mafia",
            })

            mock_client.post.assert_called_once_with(
                "/api/cards/memory",
                json={
                    "name": "Morning at Penthouse",
                    "content": "Lilith woke up to find Dante still holding her.",
                    "frontmatter": {"belongs_to": "Lilith", "importance": "high"},
                },
                params={"rp_folder": "Mafia"},
            )
            data = json.loads(result[0].text)
            assert data["name"] == "Morning at Penthouse"

    @pytest.mark.asyncio
    async def test_without_frontmatter(self):
        with _patch_client() as (mock_client, _):
            mock_client.post.return_value = _mock_response({"name": "Test"})

            await handle_create_card({
                "card_type": "knowledge",
                "name": "Test",
                "content": "Test content.",
            })

            call_args = mock_client.post.call_args
            body = call_args.kwargs["json"]
            assert "frontmatter" not in body


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_http_error_returns_error_text(self):
        """HTTP status errors are caught and returned as text, not raised."""
        with _patch_client() as (mock_client, _):
            error = _mock_error_response(404, '{"detail":"NPC not found"}')
            mock_client.post.side_effect = error

            result = await call_tool("get_npc_reaction", {
                "npc_name": "Nobody",
                "scene_prompt": "test",
                "rp_folder": "Mafia",
            })

            assert len(result) == 1
            assert "API error (404)" in result[0].text
            assert "NPC not found" in result[0].text

    @pytest.mark.asyncio
    async def test_connection_error_returns_helpful_message(self):
        """Connection errors tell the user the server might not be running."""
        with _patch_client() as (mock_client, _):
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")

            result = await call_tool("list_npcs", {"rp_folder": "Mafia"})

            assert len(result) == 1
            assert "Connection error" in result[0].text
            assert "rp-engine" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Unknown tool names return an error message."""
        result = await call_tool("nonexistent_tool", {})

        assert len(result) == 1
        assert "Unknown tool: nonexistent_tool" in result[0].text

    @pytest.mark.asyncio
    async def test_generic_exception_returns_error(self):
        """Unexpected exceptions are caught and returned as text."""
        with _patch_client() as (mock_client, _):
            mock_client.get.side_effect = ValueError("something broke")

            result = await call_tool("get_state", {"rp_folder": "Mafia"})

            assert len(result) == 1
            assert "Error: something broke" in result[0].text

    @pytest.mark.asyncio
    async def test_http_422_validation_error(self):
        """Validation errors from the API are surfaced."""
        with _patch_client() as (mock_client, _):
            error = _mock_error_response(
                422,
                '{"detail":[{"msg":"field required","type":"missing"}]}',
            )
            mock_client.post.side_effect = error

            result = await call_tool("save_exchange", {
                "user_message": "test",
                "assistant_response": "test",
                "exchange_number": 1,
            })

            assert "API error (422)" in result[0].text
            assert "field required" in result[0].text

    @pytest.mark.asyncio
    async def test_http_500_server_error(self):
        """Server errors are surfaced with status code."""
        with _patch_client() as (mock_client, _):
            error = _mock_error_response(500, "Internal Server Error")
            mock_client.post.side_effect = error

            result = await call_tool("get_scene_context", {
                "user_message": "test",
                "rp_folder": "Mafia",
            })

            assert "API error (500)" in result[0].text


# ---------------------------------------------------------------------------
# Tool listing test
# ---------------------------------------------------------------------------


class TestToolListing:
    @pytest.mark.asyncio
    async def test_list_tools_returns_14(self):
        """All 14 tools are registered."""
        from rp_engine.mcp_wrapper import list_tools

        tools = await list_tools()
        assert len(tools) == 14

    @pytest.mark.asyncio
    async def test_all_tools_have_names_and_descriptions(self):
        from rp_engine.mcp_wrapper import list_tools

        tools = await list_tools()
        for tool in tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, f"Tool {tool.name} must have a description"
            assert tool.inputSchema, f"Tool {tool.name} must have an inputSchema"

    @pytest.mark.asyncio
    async def test_tool_names_match_handlers(self):
        """Every tool name in TOOLS has a corresponding handler."""
        from rp_engine.mcp_wrapper import TOOLS, _HANDLERS

        tool_names = {t.name for t in TOOLS}
        handler_names = set(_HANDLERS.keys())
        assert tool_names == handler_names, (
            f"Mismatch: tools={tool_names - handler_names}, "
            f"handlers={handler_names - tool_names}"
        )


# ---------------------------------------------------------------------------
# Dispatch table test
# ---------------------------------------------------------------------------


class TestCallToolDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(self):
        """call_tool routes to the right handler based on name."""
        with _patch_client() as (mock_client, _):
            mock_client.get.return_value = _mock_response(
                {"npc_name": "Dante", "trust_score": 10, "trust_stage": "guarded"}
            )

            result = await call_tool("check_trust_level", {
                "npc_name": "Dante",
                "rp_folder": "Mafia",
            })

            data = json.loads(result[0].text)
            assert data["trust_score"] == 10
            # Verify it called GET (not POST)
            mock_client.get.assert_called_once()
            mock_client.post.assert_not_called()
