# Client Integration Guide

How to integrate with the RP Engine API. The API follows a "smart API, dumb client" pattern — send raw text, get structured intelligence back.

## The 3-Step Per-Turn Flow

Every RP turn follows this cycle:

### Step 1: Get Context (Before Generation)

```
POST /api/context?rp_folder=MyRP&branch=main
{
  "user_message": "She pushed through the door of the bar, scanning the room.",
  "last_response": "..." // optional: your previous RP response
}
```

**Returns:**
- `documents` — Relevant story cards (characters, locations, secrets, memories)
- `npc_briefs` — Behavioral directions for active NPCs (trust level, archetype, emotional state, what they'd do)
- `character_states` — Current conditions, locations, emotional states
- `scene_state` — Current scene context (location, time, mood)
- `thread_alerts` — Active plot threads nearing thresholds
- `triggered_notes` — Scene-specific guidance from trigger conditions
- `card_gaps` — Entity mentions missing story cards
- `current_exchange` — Exchange number (needed for Step 3)
- `guidelines` — RP-specific writing rules (POV mode, tense, etc.)

### Step 2: Generate Response (During Generation)

Use the context to write your RP response. Key usage:

- **`documents`**: Include relevant card content in your context window
- **`npc_briefs`**: Use as behavioral constraints for NPC dialogue/actions
- **`triggered_notes`**: Follow scene-specific guidance
- **`character_states`**: Reference current conditions/locations

**Optional — For important NPC moments:**
```
POST /api/npc/react?rp_folder=MyRP
{
  "npc_name": "Dante Moretti",
  "scene_prompt": "Lilith just told Dante she's leaving the organization.",
  "pov_character": "Lilith"
}
```

This calls an LLM to generate a full NPC reaction: internal monologue, physical action, dialogue, emotional undercurrent, trust shift.

### Step 3: Save Exchange (After Generation)

```
POST /api/exchanges
{
  "user_message": "She pushed through the door of the bar...",
  "assistant_response": "The bartender glanced up as the door...",
  "exchange_number": 6
}
```

**CRITICAL:**
- `assistant_response` must contain ONLY RP narrative text
- Strip all thinking blocks, tool call results, meta commentary
- Do NOT save meta discussions, OOC chat, or system conversations
- `exchange_number` = `current_exchange + 1` from Step 1

The save returns immediately. Background analysis extracts:
- State changes (character movements, emotional shifts)
- Trust modifications
- Significant events
- Plot thread progression
- In-story timestamp

## Python Example Client

```python
import httpx

API = "http://localhost:3000"
RP = "MyRP"

async def rp_turn(user_message: str, last_response: str | None = None) -> dict:
    async with httpx.AsyncClient(base_url=API, timeout=60.0) as client:
        # Step 1: Get context
        context_body = {"user_message": user_message}
        if last_response:
            context_body["last_response"] = last_response

        ctx = await client.post(
            "/api/context",
            json=context_body,
            params={"rp_folder": RP},
        )
        ctx.raise_for_status()
        context = ctx.json()

        # Step 2: Generate response using context
        # (your LLM call here, using context["documents"], context["npc_briefs"], etc.)
        assistant_response = "..."  # LLM output

        # Step 3: Save exchange
        save = await client.post("/api/exchanges", json={
            "user_message": user_message,
            "assistant_response": assistant_response,
            "exchange_number": context["current_exchange"] + 1,
        })
        save.raise_for_status()

        return {"context": context, "response": assistant_response, "saved": save.json()}
```

## Session Management

```python
# Start a session
resp = await client.post("/api/sessions", json={"rp_folder": "MyRP"})
session = resp.json()

# ... do RP turns ...

# End session (get summary data)
resp = await client.post(f"/api/sessions/{session['id']}/end")
summary = resp.json()
# summary contains: events, trust_changes, new_entities, plot_thread_status
```

## Story Card Management

```python
# List cards
resp = await client.get("/api/cards", params={"rp_folder": "MyRP"})

# Audit for missing cards
resp = await client.post("/api/cards/audit", json={"rp_folder": "MyRP"})

# Generate a draft card
resp = await client.post("/api/cards/suggest", json={
    "entity_name": "The Raven Hotel",
    "card_type": "location",
    "rp_folder": "MyRP",
})

# Create a card
resp = await client.post(
    "/api/cards/location",
    json={"name": "The Raven Hotel", "frontmatter": {"importance": "high"}, "content": "A seedy hotel..."},
    params={"rp_folder": "MyRP"},
)
```

## Error Handling

The API uses standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created (new exchange, card, session) |
| 400 | Bad request (missing required fields) |
| 404 | Not found (NPC, session, card) |
| 409 | Conflict (exchange number collision, card already exists) |
| 422 | Validation error (malformed frontmatter, invalid card type) |

Error responses include a `detail` field:
```json
{"detail": "No active session"}
{"detail": {"error": "exchange_conflict", "message": "...", "latest_exchange": 5}}
```
