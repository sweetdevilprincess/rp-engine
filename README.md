# RP Engine

REST API for managing roleplay sessions. Smart API, dumb client — the API owns all intelligence (entity extraction, context retrieval, NPC reactions, state management, response analysis).

## Prerequisites

- Python 3.12+
- pip

## Quick Start

```bash
# Install
cd rp-engine
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY=your-key-here

# Run server
uvicorn rp_engine.main:app --reload --port 3000

# API docs
open http://localhost:3000/docs
```

## Create Your First RP

```bash
# Create an RP
curl -X POST http://localhost:3000/api/rp \
  -H "Content-Type: application/json" \
  -d '{"rp_name": "MyRP"}'

# Start a session
curl -X POST http://localhost:3000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"rp_folder": "MyRP"}'

# Get context for an RP turn
curl -X POST "http://localhost:3000/api/context?rp_folder=MyRP" \
  -H "Content-Type: application/json" \
  -d '{"user_message": "She walked into the bar."}'
```

## Running Tests

```bash
pytest              # Full suite
pytest -x           # Stop on first failure
pytest -k "test_trust"  # By name pattern
```

## Architecture

**Core loop (per RP turn):**
1. `POST /api/context` — Send user message, get everything (cards, NPC briefs, state, alerts)
2. LLM generates RP response using context
3. `POST /api/exchanges` — Save exchange (triggers async analysis)

**Key design decisions:**
- SQLite with WAL mode (single file, concurrent reads)
- Async write queue (writes serialized, reads parallel)
- Story cards = markdown files (source of truth for definitions)
- Database = source of truth for runtime state
- LLM calls via OpenRouter (configurable models per function)
- Background analysis pipeline (exchange save returns immediately)

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/context` | POST | Main intelligence endpoint — send user message, get context |
| `/api/exchanges` | POST | Save RP exchange (triggers async analysis) |
| `/api/npc/react` | POST | Get single NPC reaction (LLM) |
| `/api/npc/react-batch` | POST | Batch NPC reactions |
| `/api/npc/{name}/trust` | GET | Check NPC trust level |
| `/api/npcs` | GET | List all NPCs |
| `/api/state` | GET | Full state snapshot |
| `/api/context/continuity` | GET | Continuity brief |
| `/api/context/resolve` | POST | Graph traversal resolution |
| `/api/cards` | GET | List story cards |
| `/api/cards/audit` | POST | Audit for missing cards |
| `/api/cards/suggest` | POST | Generate draft card (LLM) |
| `/api/cards/{type}` | POST | Create new card |
| `/api/sessions` | POST | Start session |
| `/api/sessions/{id}/end` | POST | End session (returns summary) |
| `/api/context/guidelines` | GET | Get RP guidelines |
| `/api/context/guidelines/system-prompt` | GET | Get default system prompt |
| `/health` | GET | Health check |

See `http://localhost:3000/docs` for full interactive API documentation.

## Configuration

Configuration via `config.yaml` with environment variable overrides:

| Setting | Env Var | Default |
|---------|---------|---------|
| API Key | `OPENROUTER_API_KEY` | (required) |
| Server Port | - | 3000 |
| Vault Root | - | `..` (parent directory) |
| DB Path | - | `data/rp-engine.db` |

## MCP Integration

The API includes an MCP wrapper for Claude Code integration:

```json
{
  "mcpServers": {
    "rp-engine": {
      "command": "python",
      "args": ["rp-engine/rp_engine/mcp_wrapper.py"]
    }
  }
}
```

Set `RP_ENGINE_URL` and `RP_FOLDER` environment variables for the MCP server.

## Docs

- [Client Integration Guide](docs/client-guide.md) — Per-turn flow and Python example
- [System Prompt Guide](docs/system-prompt-guide.md) — What to include in LLM system prompts
- [CLAUDE.md Template](docs/rp-claude-md-template.md) — Template for RP sessions using MCP tools
