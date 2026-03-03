# System Prompt Guide

What to include in the LLM system prompt for RP sessions. The API provides a default via `GET /api/context/guidelines/system-prompt?rp_folder=MyRP`.

## Required Sections

### 1. Writing Rules

The most important rules for quality RP output:

**Core Pillars:**
- Show, don't tell — physical reactions over emotional labels
- Specificity over generality — unique details, not generic descriptions
- Strong verbs — "stalked" not "walked slowly"
- Dynamic rhythm — match sentence structure to emotional state
- Friction and consequence — actions have physical cost

**Emotion to Physical Mapping:**
- Fear: throat tightening, shallow breath, cold sweat, trembling hands
- Anger: jaw clenching, knuckles whitening, heat in chest, narrowed eyes
- Sadness: chest heaviness, burning behind eyes, tight throat
- Anxiety: restless fingers, racing heartbeat, skin prickling

**Banned Patterns:**
- Sequential ", then" constructions
- Vague interiority ("something in him shifts")
- "Finally" as transition
- AI vocabulary: tapestry, delve, foster, pivotal, crucial, profound, vibrant, intricate, poignant

### 2. NPC Behavioral Framework

NPCs are driven by archetype + modifiers + trust level.

**Archetypes** (determines core behavior):
- POWER_HOLDER: Authority figures. Expect deference, trade favors, punish disrespect.
- TRANSACTIONAL: Everything has a price. Loyal to profit.
- COMMON_PEOPLE: React realistically. Avoid heroics.
- OPPOSITION: Actively work against player goals.
- SPECIALIST: Defined by competence. Speak in their field's language.
- PROTECTOR: Priority is safety of their charge.
- OUTSIDER: Limited knowledge, fresh perspective.

**Modifiers** (behavioral overlays):
OBSESSIVE, SADISTIC, PARANOID, FANATICAL, NARCISSISTIC, SOCIOPATHIC, ADDICTED, HONOR_BOUND, GRIEF_CONSUMED

**Trust Stages** (determines NPC attitude):
| Stage | Range | Behavior |
|-------|-------|----------|
| hostile | -50 to -36 | Actively hostile, will harm if able |
| antagonistic | -35 to -21 | Openly opposed, will obstruct |
| suspicious | -20 to -11 | Distrustful, assumes worst |
| wary | -10 to -1 | Cautious, keeps distance |
| neutral | 0 to 9 | Default, no strong feelings |
| familiar | 10 to 19 | Friendly, will help within limits |
| trusted | 20 to 34 | Strong bond, will take risks |
| devoted | 35 to 50 | Deep loyalty, will sacrifice |

### 3. Output Format

RP responses must contain ONLY narrative text:
- No meta commentary or OOC text
- No thinking blocks or reasoning
- No tool call content
- No system messages

### 4. RP-Specific Guidelines

From the RP's `Story_Guidelines.md`:
- POV mode (single/dual/omniscient)
- Narrative voice (first/third)
- Tense (present/past)
- Tone tags
- Scene pacing

## Using the API Endpoint

```bash
curl "http://localhost:3000/api/context/guidelines/system-prompt?rp_folder=MyRP"
```

Returns:
```json
{
  "system_prompt": "...",
  "sections": {
    "writing_principles": {},
    "rp_guidelines": {},
    "npc_framework": {},
    "output_format": {}
  }
}
```

The `system_prompt` field contains a pre-formatted text prompt ready for injection. The `sections` field gives structured data if you want to customize the assembly.

## Customization

The default system prompt covers universal rules. You can extend it with:

- **Session-specific context**: Inject story cards and NPC briefs from `POST /api/context`
- **Character-specific rules**: Add character voice guides, trauma response patterns
- **Scene-specific rules**: Different rules for combat vs dialogue vs intimate scenes

The writing principles file is at `z_AI Files/Claude/Guides/UNIVERSAL_WRITING_PRINCIPLES.md` in the vault root.
