#!/usr/bin/env python3
"""Seed the Writing Intelligence database with base patterns and correction pairs.

Reads pattern definitions inline (ported from the Writing Style Guide, Exemplars,
and Feedback/Critique Processing documents) and creates:
- 22 base patterns across 14 categories
- 11 correction pairs with before/after examples

Usage:
    python import_writing_data.py [--db-path PATH]
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from writing_intelligence.db import PatternDB
from writing_intelligence.types import (
    CorrectionPair, Direction, Pattern, PatternCategory,
)


BASE_PATTERNS = [
    # ── Pattern 1: Direct Sensory Language Over Figurative Comparison ─────
    {
        "id": "ws-figurative-simile-density",
        "category": PatternCategory.FIGURATIVE_LANGUAGE,
        "subcategory": "simile_density",
        "description": (
            "In visceral, high-intensity, or physically grounded moments, things ARE — "
            "they are not LIKE something else. Simile and metaphor create distance by asking "
            "the reader to process a comparison instead of living the moment. Figurative "
            "language is rationed, not banned. One simile in a full action sequence is fine "
            "if it earns its place. In moments of peak intensity, default to zero."
        ),
        "direction": Direction.AVOID,
        "severity": 0.9,
        "triggers": [
            "action", "high", "physical_action", "sensory_detail",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "No similes during visceral action. Things ARE, not LIKE. "
            "One per sequence max. At peak intensity, zero."
        ),
    },
    # ── Pattern 2: Sensation Before Comprehension ─────────────────────────
    {
        "id": "ws-info-order-sensation-first",
        "category": PatternCategory.INFORMATION_ORDERING,
        "subcategory": "sensation_before_comprehension",
        "description": (
            "When a character experiences something sudden, lead with the sensory experience. "
            "Delay identification. The reader should feel the hit before they know what caused "
            "it. This principle is register-agnostic — it works in survival horror, grief, "
            "comedy, and mundanity. Experience first, identification second."
        ),
        "direction": Direction.PREFER,
        "severity": 0.9,
        "triggers": [
            "action", "high", "medium", "low",
            "physical_action", "sensory_detail", "emotional_beat",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Lead with sensory experience, delay identification. "
            "The reader discovers what happened at the same moment the character does."
        ),
    },
    # ── Pattern 2a: Memory Intrusion ──────────────────────────────────────
    {
        "id": "ws-info-order-memory-intrusion",
        "category": PatternCategory.INFORMATION_ORDERING,
        "subcategory": "memory_intrusion",
        "description": (
            "When a sense memory hits a character involuntarily, the memory should interrupt "
            "the prose the same way it interrupts the character's train of thought. Break the "
            "paragraph. Let the intrusion exist on its own line. Do not fold it into the "
            "surrounding narration."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "introspection", "emotional_beat", "internal_thought",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Memory intrusions break the paragraph. The structural interruption "
            "mirrors the emotional one. The gap is where the feeling lives."
        ),
    },
    # ── Pattern 2b: Cognitive Gating by Physical State ────────────────────
    {
        "id": "ws-info-order-cognitive-gating",
        "category": PatternCategory.INFORMATION_ORDERING,
        "subcategory": "cognitive_gating",
        "description": (
            "A character's physical condition determines what thoughts are available to them. "
            "Sensation and body memory are always available. Abstract self-awareness requires "
            "executive function that physical impairment suppresses. The physical state gates "
            "the thought. Impairment can also destroy thoughts mid-formation — the reader "
            "watches the insight coalesce and dissolve."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "action", "high",
            "physical_action", "internal_thought", "emotional_beat",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Physical state gates cognition. Impaired characters lose access to abstract "
            "reasoning. Body memory stays. Executive function goes."
        ),
    },
    # ── Pattern 3: Details That Do Double Work ────────────────────────────
    {
        "id": "ws-detail-functional",
        "category": PatternCategory.DETAIL_SELECTION,
        "subcategory": "functional_detail",
        "description": (
            "Every sensory detail must serve the narrative or emotional arc beyond simple "
            "atmosphere. If a detail only describes what's there without doing additional "
            "work, it's dead weight. Cut it or replace it with something that pulls more "
            "than its own weight."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "description", "environmental_description", "sensory_detail",
            "character_description",
            "drafting", "continuing", "revising",
        ],
        "compressed_rule": (
            "Every detail must do double work — serve narrative AND emotional arc. "
            "If it only sets the scene, cut it."
        ),
    },
    # ── Pattern 3a: Motif as Thread ───────────────────────────────────────
    {
        "id": "ws-detail-motif-threading",
        "category": PatternCategory.DETAIL_SELECTION,
        "subcategory": "motif_threading",
        "description": (
            "A single sensory detail can serve as connective tissue for an entire scene when "
            "returned to with escalating emotional weight each time. Each recurrence must add "
            "a new layer of meaning. This is not repetition for its own sake."
        ),
        "direction": Direction.PREFER,
        "severity": 0.6,
        "triggers": [
            "emotional_beat", "sensory_detail",
            "description", "introspection",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Return to a single sensory detail across the scene with escalating emotional "
            "weight. Each recurrence adds a new layer."
        ),
    },
    # ── Pattern 4: Trust the Reader ───────────────────────────────────────
    {
        "id": "ws-trust-over-explanation",
        "category": PatternCategory.READER_TRUST,
        "subcategory": "over_explanation",
        "description": (
            "Do not explain what the reader can infer from context. If the prose shows blood "
            "in the water, do not state the character is bleeding. If hands shake and breath "
            "is ragged, do not say they were afraid. Show the physical manifestation. Do not "
            "label the emotion."
        ),
        "direction": Direction.AVOID,
        "severity": 0.8,
        "triggers": [
            "action", "description", "introspection",
            "high", "medium",
            "emotional_beat", "physical_action",
            "drafting", "continuing", "revising",
        ],
        "compressed_rule": (
            "Don't explain what the reader can infer. Show physical manifestation, "
            "never label the emotion."
        ),
    },
    # ── Pattern 4a: Comprehension Gap ─────────────────────────────────────
    {
        "id": "ws-trust-comprehension-gap",
        "category": PatternCategory.READER_TRUST,
        "subcategory": "comprehension_gap",
        "description": (
            "When the reader understands something the character hasn't grasped yet, the "
            "distance between the two is active narrative tension. Do not reduce it by having "
            "the character almost-get-there. A character flinching for the wrong reason while "
            "the reader holds the right reason creates a gap the reader inhabits."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "introspection", "internal_thought",
            "emotional_beat",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Don't show the character almost reaching the insight. The reader's awareness "
            "of the gap IS the tension. Let the absence do the work."
        ),
    },
    # ── Pattern 4b: Wound Memory vs Reader Reminder ───────────────────────
    {
        "id": "ws-trust-wound-memory",
        "category": PatternCategory.READER_TRUST,
        "subcategory": "wound_memory",
        "description": (
            "When a past wound drives present behavior, the memory should hit the character "
            "raw, triggered by a sensory parallel. It should not read as the author reminding "
            "the reader the wound exists. A neatly assembled list of parallels is a catalog. "
            "A character snagging on one word and spiraling into concrete sensory details is "
            "a person reliving it."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "introspection", "internal_thought", "emotional_beat",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Wound memory spirals from one sensory trigger into specific concrete details. "
            "Never present as an assembled catalog of parallels."
        ),
    },
    # ── Pattern 5: Sentence Rhythm and Fragmentation ──────────────────────
    {
        "id": "ws-pacing-rhythm-variation",
        "category": PatternCategory.PACING,
        "subcategory": "rhythm_variation",
        "description": (
            "Vary sentence length deliberately. Short fragments create pace and impact in "
            "high-intensity passages. Longer sentences slow the reader for moments needing "
            "weight. Single-word beats force the reader to pause. The shift between fragments "
            "and full sentences IS the pacing."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "action", "high", "medium",
            "physical_action", "emotional_beat", "sensory_detail",
            "drafting", "continuing", "revising",
        ],
        "compressed_rule": (
            "Fragments for impact and speed. Full sentences for weight and grounding. "
            "The structural shift IS the pacing. Single-word beats at peak moments only."
        ),
    },
    # ── Pattern 6a: LLM Tells — Words ────────────────────────────────────
    {
        "id": "ws-word-llm-tell-words",
        "category": PatternCategory.WORD_CHOICE,
        "subcategory": "llm_tell_words",
        "description": (
            "These words read as AI-generated. Avoid entirely unless context absolutely "
            "demands the specific word: tapestry (as metaphor), delve/delved, testament "
            "(as in 'a testament to'), myriad, ethereal, visceral, palpable (especially "
            "'the tension was palpable'), unwavering, relentless (standalone without earning it)."
        ),
        "direction": Direction.AVOID,
        "severity": 0.9,
        "triggers": [
            "drafting", "continuing", "revising", "expanding",
            "action", "dialogue", "introspection", "description",
            "exposition", "transition",
        ],
        "compressed_rule": (
            "Ban: tapestry (metaphor), delve, testament, myriad, ethereal, visceral, "
            "palpable, unwavering, relentless (unearned)."
        ),
    },
    # ── Pattern 6b: LLM Tells — Constructions ────────────────────────────
    {
        "id": "ws-word-llm-tell-constructions",
        "category": PatternCategory.WORD_CHOICE,
        "subcategory": "llm_tell_constructions",
        "description": (
            "These constructions read as AI-generated. Avoid: \"couldn't help but [verb]\", "
            "\"a [noun] that spoke to/of [abstract]\", \"sent a shiver down spine\", "
            "\"[noun] danced across [noun]\", \"the weight of [abstract]\" (unless literal), "
            "\"little did [subject] know\", \"[subject] found themselves [verb]ing\", "
            "\"it was as if [extended metaphor]\", \"the world/time seemed to [verb]\"."
        ),
        "direction": Direction.AVOID,
        "severity": 0.9,
        "triggers": [
            "drafting", "continuing", "revising", "expanding",
            "action", "dialogue", "introspection", "description",
            "exposition", "transition",
        ],
        "compressed_rule": (
            "Ban: 'couldn't help but', 'spoke to/of', 'shiver down spine', "
            "'danced across', 'weight of [abstract]', 'found themselves', 'as if', "
            "'seemed to'."
        ),
    },
    # ── Pattern 6c: LLM Tells — Structural ───────────────────────────────
    {
        "id": "ws-structure-llm-tell-structural",
        "category": PatternCategory.STRUCTURE,
        "subcategory": "llm_tell_structural",
        "description": (
            "Structural tells of AI writing: opening with poetic one-liner followed by "
            "mundane grounding; ending every paragraph on a reflective note; three "
            "descriptors in a row; bookending by echoing opening line; ending painful "
            "scenes with clean symbolic comfort images; using framework/system language "
            "in character interiority; cataloging character's usual behaviors to show "
            "contrast with current state (the Authored Inventory); spelling out a POV "
            "character's tactical read of another person in analytical paragraphs instead "
            "of letting actions and dialogue demonstrate the read (the Narrated Assessment). "
            "Smart characters prove intelligence through action, not through the author "
            "explaining how smart their observations are."
        ),
        "direction": Direction.AVOID,
        "severity": 0.9,
        "triggers": [
            "drafting", "continuing", "revising",
            "opening", "closing", "climax", "falling",
            "introspection", "internal_thought",
            "dialogue", "action",
        ],
        "compressed_rule": (
            "No poetic openers \u2192 mundane follow-up. No reflective paragraph endings. "
            "No triple descriptors. No bookend echoes. No comfort images on raw scenes. "
            "No system language in character thought. No authored inventories. "
            "No narrated assessments \u2014 let the response prove the read."
        ),
    },
    # ── Pattern 7: Emotional Logic Chains ─────────────────────────────────
    {
        "id": "ws-emotion-causal-chains",
        "category": PatternCategory.EMOTIONAL_LOGIC,
        "subcategory": "causal_chains",
        "description": (
            "When a character's emotional state is complex, walk the reader through each "
            "link in the reasoning. Do not jump from sensation to conclusion. Each step "
            "earns the next. Sustain multiple parallel chains \u2014 each with its own internal "
            "progression. The interplay between them is where depth lives."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "introspection", "emotional_beat", "internal_thought",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Each emotional step earns the next. No jumps from sensation to conclusion. "
            "Run parallel chains with independent logic that interacts."
        ),
    },
    # ── Pattern 8: Emotion as Active Resistance ───────────────────────────
    {
        "id": "ws-emotion-resistance-failure",
        "category": PatternCategory.EMOTIONAL_RESISTANCE,
        "subcategory": "resistance_and_failure",
        "description": (
            "Show the character fighting what they're feeling, not just experiencing it. "
            "The emotional truth lives in the resistance and its failure. Passive experience "
            "reads as performed. Active resistance that fails reads as real. The collapse "
            "means nothing if there was no wall to collapse."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "introspection", "emotional_beat", "internal_thought",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Show the character fighting the feeling and losing. The erosion of control "
            "IS the emotion. Passive experience reads as authored."
        ),
    },
    # ── Pattern 9: Environmental Pressure on Emotional Wounds ─────────────
    {
        "id": "ws-environment-world-antagonist",
        "category": PatternCategory.ENVIRONMENTAL_PRESSURE,
        "subcategory": "world_as_antagonist",
        "description": (
            "When a character's emotional state is driven by conflict with their surroundings, "
            "the environment must actively embody the source of that conflict. Other characters, "
            "objects, rituals, and spaces aren't backdrop \u2014 they are pressure applied to a "
            "specific wound. Don't just establish the environmental element \u2014 show it pushing "
            "the character toward breaking point or decision."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "description", "introspection",
            "environmental_description", "emotional_beat",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Environment isn't backdrop. It's active pressure on a specific wound. "
            "Show it pushing the character toward their breaking point."
        ),
    },
    # ── Pattern 10: Sensory Restraint as Characterization ─────────────────
    {
        "id": "ws-sensory-mundanity",
        "category": PatternCategory.SENSORY_RESTRAINT,
        "subcategory": "mundanity_as_characterization",
        "description": (
            "When a character's relationship to their environment is defined by how "
            "unremarkable it is to them, withholding sensory detail does more work than "
            "adding it. The absence of reaction to extraordinary surroundings tells the "
            "reader the character has been here long enough that it's just Tuesday. "
            "If vivid description would undermine the character's established relationship "
            "with the environment, the restraint IS the characterization."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "description", "environmental_description",
            "low", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "For familiar-to-character environments, withhold sensory detail. "
            "The reader infers history from what the prose doesn't bother to describe."
        ),
    },
    # ── Pattern 11: Performance vs Interiority ────────────────────────────
    {
        "id": "ws-performance-mask-vs-real",
        "category": PatternCategory.PERFORMANCE_INTERIORITY,
        "subcategory": "mask_vs_real",
        "description": (
            "When a character maintains an external presentation that differs from their "
            "internal state, the structural tension between the two does work regardless "
            "of register. The reader gets two layers simultaneously \u2014 the performed exterior "
            "and the real interior. In comedy, the gap generates humor. In grief, it "
            "generates the sense of a person at war with themselves."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "dialogue", "introspection", "internal_thought",
            "high", "medium", "low",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Run performed exterior and real interior in parallel. The reader sees both "
            "layers. The gap between them IS the characterization."
        ),
    },
    # ── Pattern 11a: Controlled Breach ────────────────────────────────────
    {
        "id": "ws-performance-controlled-breach",
        "category": PatternCategory.PERFORMANCE_INTERIORITY,
        "subcategory": "controlled_breach",
        "description": (
            "When a character lets their mask slip, how precisely they control the slip is "
            "itself characterization. A character who breaks only when the mic is off, or "
            "only in a single sentence before snapping back, reveals discipline and self-"
            "awareness. Distinct from emotion as active resistance \u2014 that is involuntary "
            "erosion. This is a character choosing when to open the valve and how far."
        ),
        "direction": Direction.PREFER,
        "severity": 0.6,
        "triggers": [
            "dialogue", "introspection",
            "medium", "low",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "When the mask slips, show the precision of the slip. When the mic goes off, "
            "how far the valve opens. The control characterizes as much as what's underneath."
        ),
    },
    # ── Don't resolve what isn't resolved ─────────────────────────────────
    {
        "id": "ws-structure-ending-restraint",
        "category": PatternCategory.STRUCTURE,
        "subcategory": "ending_restraint",
        "description": (
            "If a scene's emotional truth is raw and unfinished, the ending must reflect "
            "that. No symbolic closing images that provide aesthetic comfort. No reassurance. "
            "End in the body, in the moment, mid-action if necessary. The abruptness is the "
            "emotion. Painful scenes don't get pretty exits."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "closing", "falling", "climax",
            "emotional_beat",
            "high", "medium",
            "drafting", "continuing", "revising",
        ],
        "compressed_rule": (
            "Raw scenes get raw endings. No comfort images. No reassurance. "
            "End in the body. Abruptness IS the emotion."
        ),
    },
    # ── Self-directed emotion needs specific target ───────────────────────
    {
        "id": "ws-emotion-self-directed-specificity",
        "category": PatternCategory.EMOTIONAL_RESISTANCE,
        "subcategory": "self_directed_specificity",
        "description": (
            "When a character is angry or frustrated with themselves, aim the anger at the "
            "specific thing they can't stop doing or feeling, not at an abstract description "
            "of their own behavior. 'Her stupid animal body' is vague. 'You can't even be "
            "cold for one fucking day' is specific, aimed at the warmth, the stone, the need."
        ),
        "direction": Direction.PREFER,
        "severity": 0.7,
        "triggers": [
            "introspection", "internal_thought", "emotional_beat",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Self-anger targets the specific thing the character can't stop doing/feeling. "
            "Not abstract self-observation. Concrete, aimed, furious."
        ),
    },
    # ── Narrative distance — inside the body ──────────────────────────────
    {
        "id": "ws-narrative-inside-body",
        "category": PatternCategory.NARRATIVE_DISTANCE,
        "subcategory": "inside_the_body",
        "description": (
            "Write from inside the body, not from above it. The character doesn't observe "
            "their own experience \u2014 they live it. The reader should be inside the character's "
            "body, experiencing events as the character does, not observing from a distance "
            "while the author explains what's happening."
        ),
        "direction": Direction.PREFER,
        "severity": 0.8,
        "triggers": [
            "action", "introspection", "description",
            "physical_action", "emotional_beat", "sensory_detail",
            "high", "medium",
            "drafting", "continuing",
        ],
        "compressed_rule": (
            "Inside the body, not above it. Character lives the experience. "
            "Reader lives it with them. No authorial observation."
        ),
    },
]


CORRECTION_PAIRS = [
    # ── Pattern 1 pair ────────────────────────────────────────────────────
    {
        "pattern_id": "ws-figurative-simile-density",
        "original": "The cold hit like a wall of knives. Every muscle in Kael's body seized at once.",
        "revised": "Kael's muscles seized. Black water slicing into his skin as it swallowed him.",
        "critique": "Simile creates distance. Direct sensory action closes it.",
        "extracted_rule": "Describe what things DO, not what they are LIKE.",
    },
    # ── Pattern 2 pair ────────────────────────────────────────────────────
    {
        "pattern_id": "ws-info-order-sensation-first",
        "original": "His shoulder collided with something solid. A rock, jutting from the riverbed. He grabbed it.",
        "revised": "Pain erupted in his side. Something solid. Something sharp digging into his shoulder. His fingers scrambling. Rock.",
        "critique": "Original tells you what happened. Revision makes you discover it. Sensation \u2192 confusion \u2192 identification.",
        "extracted_rule": "Sensation first, identification last. Reader discovers alongside character.",
    },
    # ── Pattern 2a pair ───────────────────────────────────────────────────
    {
        "pattern_id": "ws-info-order-memory-intrusion",
        "original": (
            "He would have hated the stillness. She remembered his laugh \u2014 that sharp, "
            "startled sound \u2014 and the way the statue's frozen pose was nothing like the "
            "man she knew."
        ),
        "revised": (
            "He'd have gone red up to his ears, laughed in that sharp, startled way that "
            "meant he didn't know what to do.\n"
            "*Oh god his laugh.*\n"
            "The stillness. Frozen mid-stride with one hand raised and his jaw set like "
            "he knew what he was doing."
        ),
        "critique": (
            "The thought about embarrassment triggers the memory of the laugh. The memory "
            "derails her. She restarts on a new line. The structural interruption mirrors "
            "the emotional one."
        ),
        "extracted_rule": "Break paragraph on involuntary memory. Don't fold it into narration.",
    },
    # ── Pattern 2b pair 1 ─────────────────────────────────────────────────
    {
        "pattern_id": "ws-info-order-cognitive-gating",
        "original": (
            "His arm tightened around her. He knew he should let go. The version of him "
            "from last night \u2014 the one who'd recognized the parallel to Frank \u2014 that "
            "version would release her. His arm stayed locked."
        ),
        "revised": (
            "His arm tightened around her. His stomach lurched. Whatever his brain had "
            "been chewing on about his own voice \u2014 gone. Just her. Just warm. Just his "
            "body running the math from the last time she'd pulled away while his eyes "
            "were closed."
        ),
        "critique": (
            "Hungover character given full abstract reasoning chain in original. "
            "Revision lets nausea kill the thought, keeping him in body memory."
        ),
        "extracted_rule": "Nausea/pain/adrenaline kills abstract thought. Body memory fills the vacuum.",
    },
    # ── Pattern 2b pair 2 ─────────────────────────────────────────────────
    {
        "pattern_id": "ws-info-order-cognitive-gating",
        "original": (
            "She drove the blade into his shoulder and twisted. Even as he screamed, she "
            "thought about what this made her. Whether the woman she'd been before would "
            "recognize what she was doing."
        ),
        "revised": (
            "She drove the blade into his shoulder and twisted. He screamed. Her ears "
            "rang. She pulled the knife free and her hand was already looking for the "
            "next opening because he was still moving and moving meant dangerous and "
            "dangerous meant again."
        ),
        "critique": (
            "Adrenaline suppresses moral reasoning. Character mid-fight can't philosophize. "
            "She's locked in threat assessment \u2192 response \u2192 reassessment loop."
        ),
        "extracted_rule": "Mid-fight: threat loop only. Moral reckoning belongs to aftermath.",
    },
    # ── Pattern 3 pair ────────────────────────────────────────────────────
    {
        "pattern_id": "ws-detail-functional",
        "original": "The dark water churned around him, cold and relentless.",
        "revised": "Red swirled around him. Seeping from the deep gashes while the water whipped around him.",
        "critique": (
            "Original only describes setting. Revision shows blood (injury), severity "
            "(deep gashes), and creates visceral image \u2014 all without saying 'he was bleeding.'"
        ),
        "extracted_rule": "Replace decorative description with details that reveal character state or advance plot.",
    },
    # ── Pattern 4 pair 1 ──────────────────────────────────────────────────
    {
        "pattern_id": "ws-trust-over-explanation",
        "original": "Red swirled in the water around him \u2014 his blood, seeping from the gashes on his palms.",
        "revised": "Red swirled around him. Seeping from the deep gashes while the water whipped around him.",
        "critique": "'his blood' spells out what red in water means. Reader already knows.",
        "extracted_rule": "If the image makes the meaning obvious, don't add an explanation.",
    },
    # ── Pattern 4 pair 2 ──────────────────────────────────────────────────
    {
        "pattern_id": "ws-trust-over-explanation",
        "original": "Fear gripped her as the creature's maw opened.",
        "revised": "Drums pounded in her ears. The beast's maw opened \u2014 a dark pit lined with dagger-points.",
        "critique": "Naming 'fear' tells the reader what to feel. Heartbeat as drums lets them feel it themselves.",
        "extracted_rule": "Replace emotion labels with physical sensations that embody the emotion.",
    },
    # ── Pattern 4b pair ───────────────────────────────────────────────────
    {
        "pattern_id": "ws-trust-wound-memory",
        "original": (
            'Right back. Sure. Right back like "just a minute" and "thanks for last '
            'night" and every other thing people say before they disappear.'
        ),
        "revised": (
            "Right back. Right back like last time when right back meant gone and all "
            "that was left was a note and a heart drawn in pen and a pillow that smelled "
            "like her for one more hour before even that was\u2014"
        ),
        "critique": (
            "Original assembles parallels. Revision spirals into a specific wound \u2014 "
            "the note, the pen, the pillow going flat."
        ),
        "extracted_rule": "One trigger word \u2192 spiral into specific sensory memory. Not a list of parallels.",
    },
    # ── Pattern 8 pair ────────────────────────────────────────────────────
    {
        "pattern_id": "ws-emotion-resistance-failure",
        "original": "Her throat tightened. Tears streamed down her face. She was overwhelmed with grief.",
        "revised": (
            "Her throat tightened. She swallowed against it. [...] A cry clung to her "
            "throat. *Do not. Do not make a sound.* [...] Voice cracking. Throat dry "
            "and sore from the days she actually screamed at the stones. [...] Heat "
            "spilling down her cheeks. [...] Drops blotting the stone beneath her face. "
            "They weren't from the sky."
        ),
        "critique": (
            "Original is passive emotional experience. Revision is staged erosion: "
            "throat tightens \u2192 swallows against it \u2192 self-command \u2192 voice cracks \u2192 "
            "tears unnamed. Character loses the fight one inch at a time."
        ),
        "extracted_rule": "Escalate through failed suppression. Each stage is a small battle being lost.",
    },
]


def seed_database(db_path: str = "data/writing_intelligence.db") -> dict:
    """Create and seed the Writing Intelligence database. Returns summary stats."""
    db = PatternDB(db_path)

    patterns_created = 0
    pairs_created = 0

    # Insert base patterns
    for pdef in BASE_PATTERNS:
        existing = db.get_pattern(pdef["id"])
        if existing:
            continue

        pattern = Pattern(
            id=pdef["id"],
            category=pdef["category"],
            subcategory=pdef["subcategory"],
            description=pdef["description"],
            direction=pdef["direction"],
            severity=pdef.get("severity", 0.5),
            proficiency=0.2,
            context_triggers=pdef["triggers"],
            compressed_rule=pdef["compressed_rule"],
        )
        db.insert_pattern(pattern)
        patterns_created += 1

    # Insert correction pairs
    for cpdef in CORRECTION_PAIRS:
        # Check if pattern exists
        pattern = db.get_pattern(cpdef["pattern_id"])
        if not pattern:
            continue

        # Check if we already have a pair for this pattern with same original
        existing_pairs = db.get_correction_pairs(cpdef["pattern_id"])
        if any(cp.original[:50] == cpdef["original"][:50] for cp in existing_pairs):
            continue

        pair = CorrectionPair(
            id=str(uuid.uuid4()),
            pattern_id=cpdef["pattern_id"],
            original=cpdef["original"],
            revised=cpdef["revised"],
            critique=cpdef.get("critique"),
            extracted_rule=cpdef.get("extracted_rule"),
        )
        db.insert_correction_pair(pair)
        pairs_created += 1

    db.close()

    return {
        "patterns_created": patterns_created,
        "total_patterns": len(BASE_PATTERNS),
        "pairs_created": pairs_created,
        "total_pairs": len(CORRECTION_PAIRS),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Writing Intelligence database")
    parser.add_argument("--db-path", default="data/writing_intelligence.db",
                        help="Path to the SQLite database file")
    args = parser.parse_args()

    result = seed_database(args.db_path)
    print(f"Writing Intelligence database seeded at: {args.db_path}")
    print(f"  Patterns created: {result['patterns_created']}/{result['total_patterns']}")
    print(f"  Correction pairs created: {result['pairs_created']}/{result['total_pairs']}")
