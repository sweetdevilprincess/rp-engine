#!/usr/bin/env python3
"""NPC Intelligence CLI — standalone harness for interactive development.

Persistent DB lives alongside this file. Run operations via subcommands.
Designed to be called from Claude Code sessions for iterative improvement.

Usage:
    python npc_intel_cli.py seed
    python npc_intel_cli.py prepare "Aldric" --archetype power_holder --trust-score -40 --scene "Player demands entry"
    python npc_intel_cli.py accept
    python npc_intel_cli.py reject --feedback "Guard shouldn't cooperate at hostile trust"
    python npc_intel_cli.py reject --feedback "Too helpful" --rewrite "The guard says nothing."
    python npc_intel_cli.py stats
    python npc_intel_cli.py patterns
    python npc_intel_cli.py pattern <id>
    python npc_intel_cli.py history
    python npc_intel_cli.py reset
"""

import argparse
import json
import sys
import textwrap
from pathlib import Path

# Add parent so npc_intelligence is importable
sys.path.insert(0, str(Path(__file__).parent))

from npc_intelligence.engine import NPCIntelligence
from npc_intelligence.types import (
    BehavioralCategory, Direction, FeedbackInput, Pattern,
)
from import_npc_data import seed_database

DB_PATH = str(Path(__file__).parent / "data" / "npc_intelligence.db")


def _ensure_dir():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def _engine() -> NPCIntelligence:
    _ensure_dir()
    return NPCIntelligence(db_path=DB_PATH)


# ── State file for tracking last prepare() context ──────────────────────
STATE_PATH = str(Path(__file__).parent / "data" / ".npc_intel_state.json")


def _save_state(data: dict):
    Path(STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(STATE_PATH).write_text(json.dumps(data, indent=2))


def _load_state() -> dict:
    p = Path(STATE_PATH)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


# ── Commands ────────────────────────────────────────────────────────────

def cmd_seed(args):
    """Seed the database with base patterns and correction pairs."""
    _ensure_dir()
    result = seed_database(DB_PATH)
    print(f"Database: {DB_PATH}")
    print(f"Patterns created: {result['patterns_created']}/{result['total_patterns']}")
    print(f"Correction pairs: {result['pairs_created']}/{result['total_pairs']}")
    if result["patterns_created"] == 0:
        print("(Already seeded -- no new patterns added)")


def cmd_reseed(args):
    """Update existing base patterns with current descriptions from import_npc_data.py.

    Preserves proficiency, frequency, and correction counts. Only updates
    description, compressed_rule, and context_triggers to match the latest
    doc content.
    """
    import json as _json
    _ensure_dir()
    from import_npc_data import BASE_PATTERNS
    from npc_intelligence.db import BehavioralPatternDB

    db = BehavioralPatternDB(DB_PATH)
    updated = 0
    created = 0

    for pdef in BASE_PATTERNS:
        existing = db.get_pattern(pdef["id"])
        if existing:
            db.conn.execute(
                "UPDATE patterns SET description = ?, compressed_rule = ?, context_triggers = ? WHERE id = ?",
                (pdef["description"], pdef["compressed_rule"], _json.dumps(pdef["triggers"]), pdef["id"]),
            )
            updated += 1
        else:
            # New pattern added to import script — seed it
            from npc_intelligence.types import Pattern
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
            created += 1

    db.conn.commit()
    db.close()
    print(f"Updated {updated} existing patterns, created {created} new patterns")


def cmd_prepare(args):
    """Classify an NPC scenario and show what would be injected."""
    engine = _engine()
    try:
        modifiers = args.modifiers.split(",") if args.modifiers else []
        modifiers = [m.strip() for m in modifiers if m.strip()]

        payload = engine.prepare(
            npc_name=args.npc_name,
            archetype=args.archetype,
            modifiers=modifiers,
            trust_stage=args.trust_stage,
            trust_score=args.trust_score,
            scene_signals=_parse_signals(args.signals) if args.signals else None,
            scene_prompt=args.scene or "",
        )

        sig = payload.behavioral_signature

        # Save state so accept/reject can find it
        _save_state({
            "npc_name": args.npc_name,
            "archetype": args.archetype,
            "modifiers": modifiers,
            "trust_stage": args.trust_stage,
            "trust_score": args.trust_score,
            "scene_prompt": args.scene or "",
            "patterns_included": payload.patterns_included,
            "has_pending": True,
        })

        # Display
        print(f"=== NPC Intelligence: {args.npc_name} ===")
        print(f"Archetype:    {sig.archetype.value}")
        print(f"Modifiers:    {', '.join(m.value for m in sig.modifiers) or 'none'}")
        print(f"Trust Stage:  {sig.trust_stage.value} (score: {args.trust_score})")
        print(f"Interaction:  {sig.interaction_type.value}")
        print(f"Scene Signals: {', '.join(s.value for s in sig.scene_signals) or 'none'}")
        print(f"Patterns:     {len(payload.patterns_included)} matched")
        print(f"Tokens:       {payload.token_count}")
        print()

        if payload.patterns_included:
            print("--- Injection Payload ---")
            print(payload.text)
        else:
            print("(No patterns matched this scenario)")
        print()
        print('> Use "accept" or "reject --feedback ..." to record outcome')
    finally:
        engine.close()


def cmd_accept(args):
    """Record that the last prepared scenario produced good output."""
    state = _load_state()
    if not state.get("has_pending"):
        print("No pending prepare() to accept. Run 'prepare' first.")
        return

    engine = _engine()
    try:
        # Re-prepare to set internal state
        modifiers = state.get("modifiers", [])
        engine.prepare(
            npc_name=state["npc_name"],
            archetype=state.get("archetype", "common_people"),
            modifiers=modifiers,
            trust_stage=state.get("trust_stage", "neutral"),
            trust_score=state.get("trust_score", 0),
            scene_prompt=state.get("scene_prompt", ""),
        )

        result = engine.record_outcome(
            output_text=args.output or "(accepted without output text)",
            accepted=True,
        )

        _save_state({**state, "has_pending": False})

        print(f"ACCEPTED -- {len(result['patterns_updated'])} patterns reinforced")
        for pid in result["patterns_updated"]:
            p = engine.get_pattern(pid)
            if p:
                print(f"  {p.id}: proficiency {p.proficiency:.2f} (+0.10)")
    finally:
        engine.close()


def cmd_reject(args):
    """Record feedback/correction for the last prepared scenario."""
    state = _load_state()
    if not state.get("has_pending"):
        print("No pending prepare() to reject. Run 'prepare' first.")
        return

    if not args.feedback:
        print("--feedback is required for reject. What was wrong?")
        return

    engine = _engine()
    try:
        # Re-prepare to set internal state
        modifiers = state.get("modifiers", [])
        engine.prepare(
            npc_name=state["npc_name"],
            archetype=state.get("archetype", "common_people"),
            modifiers=modifiers,
            trust_stage=state.get("trust_stage", "neutral"),
            trust_score=state.get("trust_score", 0),
            scene_prompt=state.get("scene_prompt", ""),
        )

        feedback = FeedbackInput(
            original_output=args.output or "(no output provided)",
            user_feedback=args.feedback,
            user_rewrite=args.rewrite,
        )
        result = engine.record_outcome(
            output_text=args.output or "(rejected)",
            accepted=False,
            feedback=feedback,
        )

        _save_state({**state, "has_pending": False})

        print(f"CORRECTED -- feedback recorded")
        if result["patterns_updated"]:
            print(f"  Patterns corrected: {result['patterns_updated']}")
        if result["patterns_created"]:
            print(f"  New patterns created: {result['patterns_created']}")
            for pid in result["patterns_created"]:
                p = engine.get_pattern(pid)
                if p:
                    print(f"    {p.id}: {p.category.value} — {p.description[:80]}")
    finally:
        engine.close()


def cmd_stats(args):
    """Show system-wide statistics."""
    engine = _engine()
    try:
        stats = engine.get_stats()
        print(f"=== NPC Intelligence Stats ===")
        print(f"Total patterns:        {stats['total_patterns']}")
        print(f"Avg proficiency:       {stats['avg_proficiency']:.3f}")
        print(f"Low proficiency (<0.4): {stats['low_proficiency_count']}")
        print(f"High severity (>0.7):  {stats['high_severity_count']}")
        print()
        if stats["by_category"]:
            print("By category:")
            for cat, count in sorted(stats["by_category"].items()):
                print(f"  {cat}: {count}")
    finally:
        engine.close()


def cmd_patterns(args):
    """List all patterns with their current proficiency."""
    engine = _engine()
    try:
        patterns = engine.list_patterns(category=args.category)
        if not patterns:
            print("No patterns found." + (" Try 'seed' first." if not args.category else ""))
            return

        print(f"{'ID':<32} {'Category':<24} {'Prof':>5} {'Sev':>4} {'Freq':>4} {'Corr':>4} {'Dir':<6}")
        print("-" * 98)
        for p in sorted(patterns, key=lambda x: x.proficiency):
            pid = p.id[:31]
            print(f"{pid:<32} {p.category.value:<24} {p.proficiency:>5.2f} {p.severity:>4.1f} {p.frequency:>4} {p.correction_count:>4} {p.direction.value:<6}")
    finally:
        engine.close()


def cmd_pattern(args):
    """Show detailed info for a single pattern."""
    engine = _engine()
    try:
        # Allow partial ID match
        all_patterns = engine.list_patterns()
        matches = [p for p in all_patterns if args.pattern_id in p.id]
        if not matches:
            print(f"No pattern matching '{args.pattern_id}'")
            return
        if len(matches) > 1:
            print(f"Multiple matches for '{args.pattern_id}':")
            for p in matches:
                print(f"  {p.id}")
            return

        p = engine.get_pattern(matches[0].id)
        print(f"=== Pattern: {p.id} ===")
        print(f"Category:     {p.category.value}")
        print(f"Subcategory:  {p.subcategory}")
        print(f"Direction:    {p.direction.value}")
        print(f"Description:  {p.description}")
        print(f"Rule:         {p.compressed_rule}")
        print(f"Severity:     {p.severity:.2f}")
        print(f"Proficiency:  {p.proficiency:.2f}")
        print(f"Frequency:    {p.frequency}")
        print(f"Corrections:  {p.correction_count}")
        print(f"Triggers:     {', '.join(p.context_triggers[:10])}" +
              (f" (+{len(p.context_triggers) - 10} more)" if len(p.context_triggers) > 10 else ""))
        if p.last_triggered:
            print(f"Last triggered: {p.last_triggered.isoformat()}")
        if p.last_corrected:
            print(f"Last corrected: {p.last_corrected.isoformat()}")

        if p.correction_pairs:
            print(f"\n--- Correction Pairs ({len(p.correction_pairs)}) ---")
            for i, cp in enumerate(p.correction_pairs, 1):
                print(f"\n  Pair {i}:")
                orig_preview = cp.original[:120].replace("\n", " ")
                rev_preview = cp.revised[:120].replace("\n", " ")
                print(f"    Before: {orig_preview}...")
                print(f"    After:  {rev_preview}...")
                if cp.critique:
                    print(f"    Why:    {cp.critique[:120]}...")
    finally:
        engine.close()


def cmd_history(args):
    """Show recent output log entries."""
    engine = _engine()
    try:
        rows = engine.db.conn.execute(
            """SELECT id, session_id, task_signature, patterns_injected,
                      user_accepted, corrections_made, created_at
               FROM output_log ORDER BY created_at DESC LIMIT ?""",
            (args.limit,),
        ).fetchall()

        if not rows:
            print("No history yet.")
            return

        print(f"=== Recent Outcomes (last {args.limit}) ===")
        for row in rows:
            sig = json.loads(row["task_signature"]) if row["task_signature"] else {}
            injected = json.loads(row["patterns_injected"]) if row["patterns_injected"] else []
            accepted = row["user_accepted"]
            status = "accepted" if accepted else ("corrected" if accepted == 0 else "pending")

            arch = sig.get("archetype", "?")
            trust = sig.get("trust_stage", "?")
            print(f"\n  {row['created_at']} | {arch}/{trust} | {len(injected)} patterns | {status}")
            if row["corrections_made"]:
                corrections = json.loads(row["corrections_made"])
                print(f"    Corrections: {corrections}")
    finally:
        engine.close()


def cmd_reset(args):
    """Delete the database and start fresh."""
    db_file = Path(DB_PATH)
    if db_file.exists():
        if not args.yes:
            resp = input(f"Delete {DB_PATH}? [y/N] ")
            if resp.lower() != "y":
                print("Cancelled.")
                return
        db_file.unlink()
        print(f"Deleted {DB_PATH}")
    else:
        print("No database to delete.")

    state_file = Path(STATE_PATH)
    if state_file.exists():
        state_file.unlink()
    print("Run 'seed' to re-initialize.")


def _parse_signals(signals_str: str) -> dict:
    """Parse 'danger=0.8,combat=0.5' into dict."""
    result = {}
    for part in signals_str.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = float(v.strip())
    return result


def main():
    parser = argparse.ArgumentParser(
        description="NPC Intelligence CLI — interactive development harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # seed
    sub.add_parser("seed", help="Seed database with base patterns")

    # reseed
    sub.add_parser("reseed", help="Update existing base patterns with latest doc content")

    # prepare
    p_prep = sub.add_parser("prepare", help="Classify NPC scenario and show injection")
    p_prep.add_argument("npc_name", help="NPC name")
    p_prep.add_argument("--archetype", "-a", default="common_people")
    p_prep.add_argument("--modifiers", "-m", default="", help="Comma-separated modifiers")
    p_prep.add_argument("--trust-stage", "-t", default="neutral")
    p_prep.add_argument("--trust-score", "-s", type=int, default=0)
    p_prep.add_argument("--scene", "-p", default="", help="Scene prompt text")
    p_prep.add_argument("--signals", default="", help="Scene signals like danger=0.8,combat=0.5")

    # accept
    p_acc = sub.add_parser("accept", help="Mark last prepare as successful")
    p_acc.add_argument("--output", "-o", default="", help="The LLM output text")

    # reject
    p_rej = sub.add_parser("reject", help="Submit correction for last prepare")
    p_rej.add_argument("--feedback", "-f", required=True, help="What was wrong")
    p_rej.add_argument("--rewrite", "-r", default="", help="Corrected version")
    p_rej.add_argument("--output", "-o", default="", help="The original LLM output")

    # stats
    sub.add_parser("stats", help="Show system statistics")

    # patterns
    p_pat = sub.add_parser("patterns", help="List all patterns")
    p_pat.add_argument("--category", "-c", default=None)

    # pattern (detail)
    p_det = sub.add_parser("pattern", help="Show pattern detail")
    p_det.add_argument("pattern_id", help="Full or partial pattern ID")

    # history
    p_hist = sub.add_parser("history", help="Show recent outcomes")
    p_hist.add_argument("--limit", "-n", type=int, default=10)

    # reset
    p_reset = sub.add_parser("reset", help="Delete database and start fresh")
    p_reset.add_argument("--yes", "-y", action="store_true")

    args = parser.parse_args()

    commands = {
        "seed": cmd_seed,
        "reseed": cmd_reseed,
        "prepare": cmd_prepare,
        "accept": cmd_accept,
        "reject": cmd_reject,
        "stats": cmd_stats,
        "patterns": cmd_patterns,
        "pattern": cmd_pattern,
        "history": cmd_history,
        "reset": cmd_reset,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
