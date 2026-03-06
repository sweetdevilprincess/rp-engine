"""Trust stage computation — single source of truth.

Used by context_engine, npc_engine, state_manager, ancestry_resolver,
branch_manager, and trigger_evaluator.
"""

from __future__ import annotations

# Trust stage thresholds — expanded -50 to 50 range with 8 stages
TRUST_STAGES = [
    (-50, -36, "hostile"),
    (-35, -21, "antagonistic"),
    (-20, -11, "suspicious"),
    (-10, -1, "wary"),
    (0, 9, "neutral"),
    (10, 19, "familiar"),
    (20, 34, "trusted"),
    (35, 50, "devoted"),
]


def trust_stage(score: int) -> str:
    """Compute trust stage from score in -50 to 50 range."""
    for low, high, stage in TRUST_STAGES:
        if low <= score <= high:
            return stage
    # Clamp to extremes
    return TRUST_STAGES[0][2] if score < TRUST_STAGES[0][0] else TRUST_STAGES[-1][2]
