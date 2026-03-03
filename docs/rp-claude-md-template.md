# CLAUDE.md — RP Session Template

> Copy this file to your RP vault root or per-RP folder. Customize the RP-specific sections.

## RP Configuration

- **RP Folder:** `{RP_NAME}`
- **POV Mode:** dual / single / omniscient
- **POV Characters:** Character A, Character B
- **Narrative Voice:** first / third
- **Tense:** present / past
- **Tone:** dark, romance, slow-burn

---

## RP Session Workflow

Every RP turn follows a 3-step cycle. This is non-negotiable.

### Step 1: Get Context (BEFORE writing)

Call `get_scene_context` with the user's message at the start of every RP turn:

```
get_scene_context(user_message="<the user's raw message>")
```

Optionally include your last RP response:
```
get_scene_context(user_message="...", last_response="<your previous response>")
```

**Use the returned data:**
- `documents` — Story card content (characters, locations, secrets, memories). Reference these for accuracy.
- `npc_briefs` — Behavioral constraints for each active NPC. Follow these for trust-appropriate reactions.
- `character_states` — Current locations, conditions, emotional states. Don't contradict these.
- `scene_state` — Current scene context (location, time of day, mood).
- `thread_alerts` — Plot threads approaching thresholds. Weave these in naturally.
- `triggered_notes` — Scene-specific guidance. Follow these directives.
- `current_exchange` — Exchange number. You'll need this for Step 3.
- `guidelines` — RP writing rules (POV, tense, etc.).

### Step 2: Write the RP Response

Write the narrative response using the context from Step 1.

**Rules:**
- Response contains ONLY RP narrative text
- No thinking blocks, tool calls, or meta commentary in the response
- Follow NPC briefs for NPC behavior (trust level, archetype, emotional state)
- Reference character_states for accurate positions/conditions
- Respect knowledge boundaries — NPCs only know what they could realistically know
- Show, don't tell — physical reactions over emotional labels

### Step 3: Save Exchange (AFTER writing)

Call `save_exchange` after every RP response:

```
save_exchange(
  user_message="<the user's message>",
  assistant_response="<your RP narrative — ONLY the narrative text>",
  exchange_number=<current_exchange + 1>
)
```

**CRITICAL:**
- `assistant_response` must be ONLY the RP narrative. Strip:
  - All thinking blocks / reasoning
  - All tool call results
  - All meta commentary / OOC text
  - All system messages
- `exchange_number` = `current_exchange + 1` from Step 1
- Do NOT save meta discussions, OOC chat, system questions, or non-RP exchanges

---

## Context Tool Usage

### What Each Field Means

| Field | What It Contains | How to Use It |
|-------|-----------------|---------------|
| `documents` | Relevant story cards | Reference for character details, location descriptions, secrets |
| `npc_briefs` | Per-NPC behavioral direction | Trust level, archetype, emotional state, what they'd do |
| `character_states` | Current conditions | Locations, emotional states, injuries, statuses |
| `scene_state` | Scene context | Location, time of day, mood, atmosphere |
| `thread_alerts` | Plot thread warnings | Threads nearing fire thresholds — weave in naturally |
| `triggered_notes` | Scene-specific directives | Specific guidance triggered by scene conditions |
| `current_exchange` | Exchange counter | Use for save_exchange (add 1) |
| `guidelines` | Writing rules | POV mode, tense, voice, tone |
| `card_gaps` | Missing story cards | Entities mentioned but lacking cards |

---

## NPC Reactions

### Routine NPC Behavior
For most NPC interactions, use the `npc_briefs` from `get_scene_context`. These include:
- Trust level and stage (hostile -> devoted)
- Archetype (POWER_HOLDER, TRANSACTIONAL, etc.)
- Current emotional state
- Behavioral direction (what the NPC would do/say)

Write NPC behavior that matches their brief. Don't make hostile NPCs friendly or wary NPCs trusting.

### Important NPC Moments
For pivotal scenes, call `get_npc_reaction` for a full LLM-generated reaction:

```
get_npc_reaction(
  npc_name="Dante Moretti",
  scene_prompt="Lilith just told Dante she's leaving the organization."
)
```

Returns: internal monologue, physical action, dialogue, emotional undercurrent, trust shift.

Only use this for significant moments — it costs an LLM call. For routine NPC presence, the briefs are sufficient.

### Multiple NPCs
When multiple NPCs react to the same event:

```
batch_npc_reactions(
  npc_names=["Dante", "Marco", "Sofia"],
  scene_prompt="A gunshot rings out in the restaurant."
)
```

---

## Session Management

### Starting a Session
Sessions are started via the API before the RP begins. The MCP tools use the active session automatically.

### Ending a Session
When the RP session is over:

```
end_session(session_id="<session_id>")
```

This returns accumulated session data:
- `significant_events` — Key events that happened
- `trust_changes` — NPC trust modifications with reasons
- `new_entities` — Entity mentions lacking story cards
- `plot_thread_status` — Thread counters at session end
- `scene_progression` — Timestamps and locations visited

### Post-Session Card Creation
Use the session summary to create persistent records:

1. **Chapter summary:**
```
create_card(
  card_type="chapter",
  name="Chapter 5 - The Confrontation",
  content="Summary of what happened...",
  frontmatter={"session_id": "...", "exchange_range": [45, 62]}
)
```

2. **Memory cards** (for significant character memories):
```
create_card(
  card_type="memory",
  name="Lilith Discovers Dante's Betrayal",
  content="The memory of finding the documents...",
  frontmatter={"belongs_to": "Lilith", "importance": "high", "emotional_tone": "betrayal"}
)
```

3. **Knowledge cards** (for information characters learned):
```
create_card(
  card_type="knowledge",
  name="Location of the Safe House",
  content="Knowledge about where the safe house is...",
  frontmatter={"belongs_to": "Lilith", "importance": "medium"}
)
```

---

## Utility Tools

### Check Trust
```
check_trust_level(npc_name="Dante Moretti")
```

### Full State Snapshot
```
get_state()
```

### Continuity Brief (every 5-8 turns)
```
get_continuity_brief(scene_summary="Lilith is negotiating with Marco at the docks")
```

### Graph Context Resolution
```
resolve_context(
  keywords=["Dante", "safe house", "betrayal"],
  scene_description="Lilith discovers the safe house location",
  max_hops=2,
  max_results=15
)
```

### Audit for Missing Cards
```
audit_story_cards()
```

### Generate a Draft Card
```
suggest_card(
  entity_name="The Obsidian Room",
  card_type="location",
  additional_context="Underground meeting place beneath the restaurant"
)
```

### List All Cards
```
list_existing_cards(card_type="character")
```

---

## Writing Rules (Quick Reference)

### Core Pillars
1. **Show, don't tell** — Physical reactions over emotional labels
2. **Specificity** — Unique details, not generic descriptions
3. **Strong verbs** — "stalked" not "walked slowly"
4. **Dynamic rhythm** — Match sentence structure to emotional state
5. **Friction and consequence** — Actions have physical cost

### Banned Patterns
- Sequential ", then" constructions
- Vague interiority ("something in him shifts")
- "Finally" as transition
- AI vocabulary: tapestry, delve, foster, pivotal, crucial, profound

### NPC Dialogue Rules
- No monologues — 2-3 sentences max per NPC speaking turn
- NPCs can be wrong, miss things, misunderstand
- NPCs prioritize self-interest
- Respect knowledge boundaries — NPCs only know what they could realistically know

For the full writing guide, see `z_AI Files/Claude/Guides/UNIVERSAL_WRITING_PRINCIPLES.md` or call `get_scene_context` which includes guidelines.

---

## Complete Tool Reference

| Tool | Purpose | Required Args | Optional Args |
|------|---------|---------------|---------------|
| `get_scene_context` | Get all context for an RP turn | `user_message` | `last_response`, `rp_folder`, `branch` |
| `save_exchange` | Save completed exchange | `user_message`, `assistant_response`, `exchange_number` | `session_id` |
| `get_npc_reaction` | Single NPC LLM reaction | `npc_name`, `scene_prompt` | `pov_character` |
| `batch_npc_reactions` | Multiple NPC reactions | `npc_names`, `scene_prompt` | `pov_character` |
| `check_trust_level` | Check NPC trust score | `npc_name` | `target_name` |
| `list_npcs` | List all NPCs | (none) | |
| `get_state` | Full state snapshot | (none) | |
| `get_continuity_brief` | Condensed continuity summary | (none) | `scene_summary`, `focus_areas` |
| `resolve_context` | Graph traversal for entities | `keywords` | `scene_description`, `max_hops`, `max_results` |
| `audit_story_cards` | Find missing story cards | (none) | `rp_folder`, `mode`, `session_id` |
| `suggest_card` | Generate draft card via LLM | `entity_name`, `card_type` | `additional_context` |
| `list_existing_cards` | List all story cards | (none) | `card_type` |
| `end_session` | End session, get summary | `session_id` | |
| `create_card` | Create new story card | `card_type`, `name`, `content` | `frontmatter` |
