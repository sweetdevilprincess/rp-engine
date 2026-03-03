#!/usr/bin/env python3
"""Seed the NPC Intelligence database with base patterns and correction pairs.

Reads the NPC behavioral framework markdown files and creates:
- 11 base patterns (one per BehavioralCategory)
- 5 correction pairs from the Exemplars document

Usage:
    python import_npc_data.py [--db-path PATH]
"""

import argparse
import uuid
from pathlib import Path

from npc_intelligence.db import BehavioralPatternDB
from npc_intelligence.types import (
    BehavioralCategory, CorrectionPair, Direction, Pattern,
    Archetype, Modifier, TrustStage, InteractionType, SceneSignal,
)


ALL_ARCHETYPES = [a.value for a in Archetype]
ALL_MODIFIERS = [m.value for m in Modifier]
ALL_TRUST_STAGES = [t.value for t in TrustStage]

BASE_PATTERNS = [
    {
        "id": "base-self-interest",
        "category": BehavioralCategory.SELF_INTEREST,
        "subcategory": "motivation",
        "description": "NPC actions require traceable motivation. Every choice must connect to what the NPC wants, fears, or protects.",
        "direction": Direction.AVOID,
        "compressed_rule": "Every action needs a self-interest reason — no unmotivated cooperation or hostility",
        "triggers": ALL_ARCHETYPES + ALL_TRUST_STAGES,
    },
    {
        "id": "base-archetype-voice",
        "category": BehavioralCategory.ARCHETYPE_VOICE,
        "subcategory": "speech-patterns",
        "description": "Each archetype has distinct verbal patterns, cognitive framing, decision-making, and emotional reactions. The archetype determines which emotion fires in response to a stimulus — not generic human defaults. A POWER_HOLDER feels interest at audacity, not offense. A SADISTIC NPC feels satisfaction at suffering, not discomfort. If the emotional reaction could belong to any character in the same situation, the archetype hasn't shaped the interiority.",
        "direction": Direction.AVOID,
        "compressed_rule": "Archetype defines how the NPC thinks, speaks, and what they FEEL — not generic human emotional defaults",
        "triggers": ALL_ARCHETYPES + ALL_MODIFIERS,
    },
    {
        "id": "base-trust-mechanics",
        "category": BehavioralCategory.TRUST_MECHANICS,
        "subcategory": "boundaries",
        "description": "Trust stages create hard behavioral boundaries. NPCs cannot exceed their cooperation ceiling for the current trust level.",
        "direction": Direction.AVOID,
        "compressed_rule": "Trust stage caps cooperation level — never exceed the ceiling",
        "triggers": ALL_TRUST_STAGES,
    },
    {
        "id": "base-escalation",
        "category": BehavioralCategory.ESCALATION,
        "subcategory": "proportional",
        "description": "NPCs escalate proportionally to provocation. Hostility follows a sequence: polite deflection, firm boundaries, institutional authority, veiled threats, controlled display, then only real violence.",
        "direction": Direction.AVOID,
        "compressed_rule": "Escalation is proportional — never skip stages without extreme provocation",
        "triggers": [
            TrustStage.HOSTILE.value, TrustStage.ANTAGONISTIC.value,
            SceneSignal.DANGER.value, SceneSignal.COMBAT.value,
            InteractionType.CONFRONTATION.value,
            InteractionType.HOSTILE_ENCOUNTER.value,
        ],
    },
    {
        "id": "base-modifier-fidelity",
        "category": BehavioralCategory.MODIFIER_FIDELITY,
        "subcategory": "persistence",
        "description": "Modifiers color everything the NPC does. They don't soften with time or familiarity — paranoid stays paranoid, obsessive stays obsessive. Each modifier has specific activation patterns: OBSESSIVE hooks on novelty not attraction, PARANOID assumes hidden networks, SADISTIC derives pleasure not discomfort. The modifier shapes which emotion fires, not just which action follows.",
        "direction": Direction.AVOID,
        "compressed_rule": "Modifiers persist permanently and shape emotions — OBSESSIVE hooks on novelty, PARANOID sees networks, SADISTIC feels pleasure",
        "triggers": ALL_MODIFIERS,
    },
    {
        "id": "base-internal-external-gap",
        "category": BehavioralCategory.INTERNAL_EXTERNAL_GAP,
        "subcategory": "mask-behavior",
        "description": "Internal monologue does not equal external behavior. NPCs maintain masks. What they think and what they show are deliberately different.",
        "direction": Direction.PREFER,
        "compressed_rule": "Show the gap between internal state and external behavior through action, not narration",
        "triggers": ALL_ARCHETYPES + ALL_MODIFIERS,
    },
    {
        "id": "base-hostility-persistence",
        "category": BehavioralCategory.HOSTILITY_PERSISTENCE,
        "subcategory": "no-thaw",
        "description": "Hostility doesn't evaporate from a single kind gesture or logical argument. Negative trust requires sustained changed behavior over multiple sessions to shift.",
        "direction": Direction.AVOID,
        "compressed_rule": "Hostile NPCs don't thaw from one good argument — distrust is earned through history",
        "triggers": [
            TrustStage.HOSTILE.value, TrustStage.ANTAGONISTIC.value,
            TrustStage.SUSPICIOUS.value, TrustStage.WARY.value,
        ],
    },
    {
        "id": "base-cooperation-ceiling",
        "category": BehavioralCategory.COOPERATION_CEILING,
        "subcategory": "trust-cap",
        "description": "Each trust stage caps the maximum cooperation level. A neutral NPC won't risk their life; a suspicious NPC won't share valuable information freely.",
        "direction": Direction.AVOID,
        "compressed_rule": "Cooperation ceiling matches trust stage — don't let good arguments bypass it",
        "triggers": ALL_TRUST_STAGES + [
            InteractionType.COOPERATION_REQUEST.value,
            InteractionType.NEGOTIATION.value,
        ],
    },
    {
        "id": "base-social-hierarchy",
        "category": BehavioralCategory.SOCIAL_HIERARCHY,
        "subcategory": "power-dynamics",
        "description": "Power differentials shape every interaction. A guard can't lecture a nobleman. A servant addresses a lord differently than a peer.",
        "direction": Direction.AVOID,
        "compressed_rule": "Social position constrains what the NPC can say and do",
        "triggers": [
            Archetype.POWER_HOLDER.value, Archetype.COMMON_PEOPLE.value,
            Archetype.TRANSACTIONAL.value, Archetype.SPECIALIST.value,
            InteractionType.SOCIAL_INTERACTION.value,
            SceneSignal.SOCIAL.value,
        ],
    },
    {
        "id": "base-hybrid-friction",
        "category": BehavioralCategory.HYBRID_FRICTION,
        "subcategory": "internal-conflict",
        "description": "Conflicting modifiers or multiple archetypes create visible internal struggle. The friction should be shown through behavior, not narrated.",
        "direction": Direction.AVOID,
        "compressed_rule": "Multiple archetypes/modifiers create friction — show the conflict in behavior",
        "triggers": ALL_MODIFIERS,
    },
    {
        "id": "base-knowledge-boundary",
        "category": BehavioralCategory.KNOWLEDGE_BOUNDARY,
        "subcategory": "information-limits",
        "description": "NPCs only know what they'd realistically know. A street vendor doesn't know state secrets. A guard knows his post, not city politics.",
        "direction": Direction.AVOID,
        "compressed_rule": "NPCs only share information they'd realistically have access to",
        "triggers": ALL_ARCHETYPES + [
            InteractionType.INFORMATION_REQUEST.value,
            SceneSignal.INVESTIGATION.value,
        ],
    },
]


# Correction pairs extracted from the Exemplars document
CORRECTION_PAIRS = [
    {
        "pattern_id": "base-archetype-voice",
        "original": (
            'Captain Aldric studied the stranger\'s face, then sighed heavily. '
            '"The restricted quarter isn\'t open to civilians. That\'s the rule." '
            'He paused, seeming to wrestle with something. "But... if someone were '
            'really missing, I suppose I could look the other way. Just this once. '
            'Be quick about it, and don\'t tell anyone I let you through."'
        ),
        "revised": (
            '"Restricted."\n\n'
            "One word. Aldric didn't look up from the logbook. The quill scratched "
            "another line — shift count, gate traffic, the small bureaucracy that "
            "kept this post running and him paid.\n\n"
            '"If you\'ve got a writ from the magistrate\'s office, present it. '
            "If you don't, the magistrate's office is on Levain Street. They open "
            'at seventh bell." He glanced up. Once. The assessment was brief and '
            'complete. "We done?"'
        ),
        "critique": (
            "POWER_HOLDER at stranger-level trust: Aldric routes to procedure, not engagement. "
            "The LLM version has him wrestling with compassion and cooperating without incentive. "
            "The corrected version shows institutional reflex — redirect to proper channels, "
            "give minimum useful information, end the interaction."
        ),
    },
    {
        "pattern_id": "base-self-interest",
        "original": (
            'Petra\'s expression shifted when she heard the request. "Moonpetal extract? '
            "That's... not something I keep on the shelf.\" She lowered her voice. "
            '"Look, you\'ve been a good customer. I can get it for you, but it\'ll take '
            "a few days and it won't be cheap. Three times the standard rate. And you "
            'didn\'t get it from me."'
        ),
        "revised": (
            '"Moonpetal." Petra repeated the word the way you\'d repeat someone\'s claim '
            "that they could fly. Flat. Evaluating. \"That what you're after.\"\n\n"
            '"You know what moonpetal draws." Not a question. "Inspectors. Questions. '
            'The kind that come with badges and a real specific interest in my supplier chain."\n\n'
            '"Now you\'re asking me to put my license on the scale. So here\'s what I need to hear '
            "before this conversation goes any further: what's in it for me that's worth more "
            'than the inspector problem?"'
        ),
        "critique": (
            "TRANSACTIONAL at Known trust: The LLM version has Petra agreeing instantly with a "
            "price markup. The corrected version shows her pricing the risk out loud and requiring "
            "the player to make the equation work. She opens a negotiation, not a transaction."
        ),
    },
    {
        "pattern_id": "base-modifier-fidelity",
        "original": (
            "Draeven's eyes darted around the room before he leaned in closer. "
            '"You want to know about the Senator\'s connections? That\'s dangerous territory." '
            "He paused, his paranoid nature warring with the trust they'd built. "
            '"Alright. But we do this my way. Back room. No names. And if anyone asks, '
            'we never spoke about this."'
        ),
        "revised": (
            '"Sit down."\n\n'
            "Draeven hadn't moved from the seat facing the door. Never did.\n\n"
            '"The Senator." He said it the way someone would say the name of a disease '
            'they were checking for.\n\n'
            '"What I want to know is who told you to want it."\n\n'
            '"Three jobs. Clean work, fair payment, no complications. That buys you my time. '
            "It doesn't buy my neck.\""
        ),
        "critique": (
            "SPECIALIST with PARANOID modifier at Known trust: The LLM version narrates "
            "'his paranoid nature warring' and then capitulates. The corrected version shows "
            "paranoia through behavior — the seat facing the door, the drink from elsewhere, "
            "the investigation of who sent the player before answering anything."
        ),
    },
    {
        "pattern_id": "base-hostility-persistence",
        "original": (
            'Serrada studied the PC with cold eyes, then let out a short, humorless laugh. '
            '"A truce. From you." She crossed her arms. "You\'ve got nerve, I\'ll give you that." '
            "A pause. Something calculating entered her expression. \"The Conclave is a problem "
            "for both of us. I won't pretend otherwise. So here's what I propose — we stay out "
            "of each other's way until they're dealt with. After that, you and I settle our "
            'business. Agreed?"'
        ),
        "revised": (
            "Serrada was already leaving.\n\n"
            "She didn't stop. Didn't turn. The conversation was something happening behind "
            "her, like weather.\n\n"
            "Her stride shortened. Not a stop. A recalculation.\n\n"
            '"If I decide the Conclave is my problem — and I haven\'t — I\'ll handle it myself." '
            "She turned back toward the door. \"The fact that you're standing here telling me "
            "about it means you can't. Which tells me everything I need to know about how useful "
            'a truce with you would be."'
        ),
        "critique": (
            "OPPOSITION at Hostile trust: The LLM version reaches a negotiated truce in one "
            "exchange with a deeply hostile NPC. The corrected version has Serrada dismiss the "
            "proposal entirely — the player's need for a truce is read as weakness, not as "
            "an opportunity for cooperation."
        ),
    },
    {
        "pattern_id": "base-hybrid-friction",
        "original": (
            'Tomas planted himself firmly in the nobleman\'s path, his hand resting on his '
            'halberd. "My lord, I understand your urgency, but my orders are clear. No one '
            "passes until the quarantine is lifted. I swore an oath to protect this city, and "
            'that includes protecting you — even from yourself." He met the nobleman\'s gaze '
            'steadily. "I mean no disrespect. But I can\'t let you through."'
        ),
        "revised": (
            '"Can\'t do that, my lord."\n\n'
            "The my lord came out right. Two years of training had made the address automatic.\n\n"
            '"Lord Hessler. Third seat on the trade council." Tomas recited it the way he\'d '
            "recite a watch report. Facts. Sequence.\n\n"
            "His hand didn't move from the halberd. His stomach moved, though. That old familiar "
            "knot. The one that showed up when the uniform made him the instrument of the same "
            "machinery that had ground down everyone he'd grown up with.\n\n"
            '"That\'s your lordship\'s right."\n\nTomas didn\'t move.'
        ),
        "critique": (
            "POWER_HOLDER + COMMON_PEOPLE with HONOR_BOUND: The LLM version gives Tomas a "
            "noble speech about oaths. The corrected version shows three archetypes in friction — "
            "the trained institutional voice (POWER_HOLDER), the class recognition of how power "
            "works (COMMON_PEOPLE), and the immovable code (HONOR_BOUND) — all through behavior, "
            "not eloquence."
        ),
    },
]


def seed_database(db_path: str = "npc_intelligence.db") -> dict:
    """Create and seed the NPC intelligence database. Returns summary stats."""
    db = BehavioralPatternDB(db_path)

    patterns_created = 0
    pairs_created = 0

    # Insert base patterns
    for pdef in BASE_PATTERNS:
        # Check if already exists
        existing = db.get_pattern(pdef["id"])
        if existing:
            continue

        pattern = Pattern(
            id=pdef["id"],
            category=pdef["category"],
            subcategory=pdef["subcategory"],
            description=pdef["description"],
            direction=pdef["direction"],
            severity=0.8,
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
        already_exists = any(
            p.original[:50] == cpdef["original"][:50] for p in existing_pairs
        )
        if already_exists:
            continue

        pair = CorrectionPair(
            id=str(uuid.uuid4()),
            pattern_id=cpdef["pattern_id"],
            original=cpdef["original"],
            revised=cpdef["revised"],
            critique=cpdef["critique"],
            tokens_original=len(cpdef["original"].split()),
            tokens_revised=len(cpdef["revised"].split()),
        )
        db.insert_correction_pair(pair)
        pairs_created += 1

    db.close()

    return {
        "patterns_created": patterns_created,
        "pairs_created": pairs_created,
        "total_patterns": len(BASE_PATTERNS),
        "total_pairs": len(CORRECTION_PAIRS),
    }


def main():
    parser = argparse.ArgumentParser(description="Seed NPC Intelligence database")
    parser.add_argument("--db-path", default="npc_intelligence.db",
                        help="Path to the SQLite database file")
    args = parser.parse_args()

    result = seed_database(args.db_path)
    print(f"NPC Intelligence database seeded at: {args.db_path}")
    print(f"  Patterns created: {result['patterns_created']}/{result['total_patterns']}")
    print(f"  Correction pairs created: {result['pairs_created']}/{result['total_pairs']}")


if __name__ == "__main__":
    main()
