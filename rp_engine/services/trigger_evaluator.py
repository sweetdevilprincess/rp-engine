"""Situational trigger evaluation engine.

Evaluates conditions defined on triggers against:
- Expression functions (any, all, none, near, count, seq) on text
- State conditions (character attributes, relationships, scene state)
- Signal conditions (scene classifier output)

Tier 1 implementation: individual conditions with match_mode (any/all).
Full infix parser deferred to fast-follow.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rp_engine.database import Database
from rp_engine.models.trigger import ConditionResult, TriggerTestResult
from rp_engine.utils.json_helpers import safe_parse_json_array

logger = logging.getLogger(__name__)

# Regex for parsing expression function calls: func("arg1","arg2",N)
_EXPR_PATTERN = re.compile(
    r'^(\w+)\s*\(\s*(.*?)\s*\)$', re.DOTALL
)
# Parse quoted string arguments
_ARG_PATTERN = re.compile(r'"([^"]*)"')

# Allowlists for dynamic column selection in _eval_state
_VALID_CHAR_FIELDS = {"location", "conditions", "emotional_state", "last_seen"}
_VALID_REL_FIELDS = {"initial_trust_score", "trust_modification_sum", "dynamic", "trust_stage"}
_VALID_SCENE_FIELDS = {"location", "time_of_day", "mood", "in_story_timestamp"}


@dataclass
class FiredTrigger:
    trigger_id: str
    trigger_name: str
    inject_type: str
    inject_content: str | None
    inject_card_path: str | None
    priority: int
    matched_conditions: list[str]


class TriggerEvaluator:
    """Evaluate situational triggers against text, state, and signals."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def evaluate_all(
        self,
        rp_folder: str,
        branch: str,
        text: str,
        signals: dict[str, float],
        current_turn: int,
    ) -> list[FiredTrigger]:
        """Load enabled triggers, evaluate each, return fired ones sorted by priority."""
        rows = await self.db.fetch_all(
            """SELECT id, name, conditions, match_mode, inject_type,
                      inject_content, inject_card_path, priority,
                      cooldown_turns, last_fired_turn
               FROM situational_triggers
               WHERE rp_folder = ? AND enabled = 1""",
            [rp_folder],
        )

        fired: list[FiredTrigger] = []
        for row in rows:
            # Check cooldown
            cooldown = row.get("cooldown_turns", 0) or 0
            last_fired = row.get("last_fired_turn")
            if last_fired is not None and cooldown > 0:
                if current_turn - last_fired < cooldown:
                    continue

            # Parse conditions JSON
            conditions = safe_parse_json_array(row.get("conditions"))
            if not conditions:
                logger.warning("Invalid conditions JSON for trigger %s", row["id"])
                continue

            # Evaluate conditions
            match_mode = row.get("match_mode", "any")
            matched_descs: list[str] = []
            all_pass = True

            for cond in conditions:
                passed, detail = await self._evaluate_condition(
                    cond, text, signals, rp_folder, branch
                )
                if passed:
                    matched_descs.append(detail)
                else:
                    all_pass = False

                if match_mode == "any" and passed:
                    break
                if match_mode == "all" and not passed:
                    break

            should_fire = (
                (match_mode == "any" and len(matched_descs) > 0) or
                (match_mode == "all" and all_pass and len(matched_descs) > 0)
            )

            if should_fire:
                fired.append(FiredTrigger(
                    trigger_id=row["id"],
                    trigger_name=row["name"],
                    inject_type=row["inject_type"],
                    inject_content=row.get("inject_content"),
                    inject_card_path=row.get("inject_card_path"),
                    priority=row.get("priority", 0) or 0,
                    matched_conditions=matched_descs,
                ))

                # Update last_fired_turn (await to ensure committed before next eval)
                future = await self.db.enqueue_write(
                    "UPDATE situational_triggers SET last_fired_turn = ? WHERE id = ?",
                    [current_turn, row["id"]],
                )
                await future

        # Sort by priority (highest first)
        fired.sort(key=lambda t: t.priority, reverse=True)
        return fired

    async def evaluate_single(
        self,
        trigger_id: str,
        text: str,
        signals: dict[str, float],
        rp_folder: str | None = None,
        branch: str = "main",
    ) -> TriggerTestResult:
        """For /test endpoint. Returns detailed per-condition results."""
        row = await self.db.fetch_one(
            "SELECT conditions, match_mode, rp_folder FROM situational_triggers WHERE id = ?",
            [trigger_id],
        )
        if not row:
            return TriggerTestResult(
                would_fire=False,
                conditions_evaluated=[],
                signals=signals,
            )

        rp = rp_folder or row.get("rp_folder", "")
        match_mode = row.get("match_mode", "any")

        conditions = safe_parse_json_array(row.get("conditions"))

        results: list[ConditionResult] = []
        for i, cond in enumerate(conditions):
            passed, detail = await self._evaluate_condition(
                cond, text, signals, rp, branch
            )
            results.append(ConditionResult(
                condition_index=i,
                condition_type=cond.get("type", "unknown"),
                matched=passed,
                detail=detail,
            ))

        any_matched = any(r.matched for r in results)
        all_matched = all(r.matched for r in results) and len(results) > 0

        would_fire = (
            (match_mode == "any" and any_matched) or
            (match_mode == "all" and all_matched)
        )

        return TriggerTestResult(
            would_fire=would_fire,
            conditions_evaluated=results,
            signals=signals,
        )

    async def _evaluate_condition(
        self,
        cond: dict,
        text: str,
        signals: dict[str, float],
        rp_folder: str,
        branch: str,
    ) -> tuple[bool, str]:
        """Evaluate a single condition. Returns (passed, detail_string)."""
        cond_type = cond.get("type", "")

        if cond_type == "expression":
            return self._eval_expression(cond.get("expr", ""), text)
        elif cond_type == "state":
            return await self._eval_state(
                cond.get("path", ""),
                cond.get("operator", "=="),
                cond.get("value"),
                cond.get("values"),
                rp_folder,
                branch,
            )
        elif cond_type == "signal":
            return self._eval_signal(
                cond.get("signal", ""),
                cond.get("operator", ">="),
                cond.get("value", 0),
                signals,
            )

        return False, f"Unknown condition type: {cond_type}"

    def _eval_expression(self, expr: str, text: str) -> tuple[bool, str]:
        """Evaluate expression functions against text."""
        if not expr:
            return False, "Empty expression"

        match = _EXPR_PATTERN.match(expr.strip())
        if not match:
            return False, f"Invalid expression syntax: {expr}"

        func_name = match.group(1).lower()
        args_str = match.group(2)

        # Parse quoted arguments
        str_args = _ARG_PATTERN.findall(args_str)
        text_lower = text.lower()

        if func_name == "any":
            for arg in str_args:
                if arg.lower() in text_lower:
                    return True, f"any() matched: '{arg}'"
            return False, f"any() no match in {str_args}"

        elif func_name == "all":
            for arg in str_args:
                if arg.lower() not in text_lower:
                    return False, f"all() missing: '{arg}'"
            return True, f"all() matched: {str_args}"

        elif func_name == "none":
            for arg in str_args:
                if arg.lower() in text_lower:
                    return False, f"none() found: '{arg}'"
            return True, f"none() confirmed absent: {str_args}"

        elif func_name == "near":
            if len(str_args) < 2:
                return False, "near() requires at least 2 string args"
            # Parse distance: last non-quoted arg
            distance = 200  # default
            remaining = args_str
            for a in str_args:
                remaining = remaining.replace(f'"{a}"', "", 1)
            nums = re.findall(r'\d+', remaining)
            if nums:
                distance = int(nums[0])

            w1, w2 = str_args[0].lower(), str_args[1].lower()
            idx1 = text_lower.find(w1)
            idx2 = text_lower.find(w2)
            if idx1 == -1 or idx2 == -1:
                return False, f"near() word not found: {'w1' if idx1 == -1 else 'w2'}"
            if abs(idx1 - idx2) <= distance:
                return True, f"near('{w1}','{w2}',{distance}) = {abs(idx1 - idx2)} chars"
            return False, f"near() too far: {abs(idx1 - idx2)} > {distance}"

        elif func_name == "count":
            if not str_args:
                return False, "count() requires a word argument"
            word = str_args[0].lower()
            n = text_lower.count(word)
            # If there's an operator in the remaining args, evaluate it
            remaining = args_str
            for a in str_args:
                remaining = remaining.replace(f'"{a}"', "", 1)
            # Look for comparison: >=N, >N, ==N, <=N, <N
            comp = re.search(r'([><=!]+)\s*(\d+)', remaining)
            if comp:
                op, val = comp.group(1), int(comp.group(2))
                result = _compare(n, op, val)
                return result, f"count('{word}') = {n} {op} {val}: {result}"
            # Default: count > 0
            return n > 0, f"count('{word}') = {n}"

        elif func_name == "seq":
            if len(str_args) < 2:
                return False, "seq() requires 2 arguments"
            w1, w2 = str_args[0].lower(), str_args[1].lower()
            idx1 = text_lower.find(w1)
            idx2 = text_lower.find(w2)
            if idx1 == -1 or idx2 == -1:
                return False, "seq() word not found"
            if idx1 < idx2:
                return True, f"seq('{w1}','{w2}'): {idx1} < {idx2}"
            return False, f"seq('{w1}','{w2}'): {idx1} >= {idx2}"

        return False, f"Unknown function: {func_name}"

    async def _eval_state(
        self,
        path: str,
        operator: str,
        value,
        values: list | None,
        rp_folder: str,
        branch: str,
    ) -> tuple[bool, str]:
        """Evaluate state conditions by querying the database.

        Path formats:
        - characters.{name}.{field}
        - relationships.{a}->{b}.{field}
        - scene.{field}
        """
        if not path:
            return False, "Empty state path"

        parts = path.split(".")

        if parts[0] == "characters" and len(parts) >= 3:
            name = parts[1]
            field_name = parts[2]
            if field_name not in _VALID_CHAR_FIELDS:
                logger.warning("Invalid character field in trigger condition: %s", field_name)
                return False, f"Invalid character field: {field_name}"
            # Look up card_id from story_cards, then query character_state_entries
            card_id = await self.db.fetch_val(
                "SELECT id FROM story_cards WHERE LOWER(name) = ? AND rp_folder = ?",
                [name.lower(), rp_folder],
            )
            if not card_id:
                return False, f"Character '{name}' not found"
            row = await self.db.fetch_one(
                f"""SELECT {field_name} FROM character_state_entries
                    WHERE card_id = ? AND rp_folder = ? AND branch = ?
                    ORDER BY exchange_number DESC LIMIT 1""",
                [card_id, rp_folder, branch],
            )
            if not row:
                return False, f"Character '{name}' has no state"

            db_val = row.get(field_name)
            return self._compare_state_value(db_val, operator, value, values, field_name)

        elif parts[0] == "relationships" and len(parts) >= 3:
            # Format: relationships.a->b.field
            rel_part = parts[1]
            field_name = parts[2]
            if "->" not in rel_part:
                return False, f"Invalid relationship path: {rel_part}"
            char_a, char_b = rel_part.split("->", 1)

            if field_name == "trust_score":
                baseline = await self.db.fetch_val(
                    """SELECT baseline_score FROM trust_baselines
                       WHERE LOWER(character_a) = ? AND LOWER(character_b) = ?
                         AND rp_folder = ? AND branch = ?""",
                    [char_a.lower(), char_b.lower(), rp_folder, branch],
                )
                mod_sum = await self.db.fetch_val(
                    """SELECT COALESCE(SUM(change), 0) FROM trust_modifications
                       WHERE LOWER(character_a) = ? AND LOWER(character_b) = ?
                         AND rp_folder = ? AND branch = ?""",
                    [char_a.lower(), char_b.lower(), rp_folder, branch],
                )
                db_val = (baseline or 0) + (mod_sum or 0)
                return self._compare_state_value(db_val, operator, value, values, field_name)
            else:
                if field_name not in _VALID_REL_FIELDS:
                    logger.warning("Invalid relationship field in trigger condition: %s", field_name)
                    return False, f"Invalid relationship field: {field_name}"
                # For non-trust_score relationship fields, check trust_baselines
                row = await self.db.fetch_one(
                    f"""SELECT {field_name} FROM trust_baselines
                        WHERE LOWER(character_a) = ? AND LOWER(character_b) = ?
                          AND rp_folder = ? AND branch = ?""",
                    [char_a.lower(), char_b.lower(), rp_folder, branch],
                )

            if not row:
                return False, f"Relationship '{char_a}->{char_b}' not found"

            db_val = row.get(field_name)
            return self._compare_state_value(db_val, operator, value, values, field_name)

        elif parts[0] == "scene" and len(parts) >= 2:
            field_name = parts[1]
            if field_name not in _VALID_SCENE_FIELDS:
                logger.warning("Invalid scene field in trigger condition: %s", field_name)
                return False, f"Invalid scene field: {field_name}"
            row = await self.db.fetch_one(
                f"""SELECT {field_name} FROM scene_state_entries
                    WHERE rp_folder = ? AND branch = ?
                    ORDER BY exchange_number DESC LIMIT 1""",
                [rp_folder, branch],
            )
            if not row:
                return False, "No scene context"

            db_val = row.get(field_name)
            return self._compare_state_value(db_val, operator, value, values, field_name)

        return False, f"Unknown state path prefix: {parts[0]}"

    def _compare_state_value(
        self, db_val, operator: str, value, values: list | None, field_name: str
    ) -> tuple[bool, str]:
        """Compare a DB value against condition using operator."""
        # Handle JSON columns (conditions, behavioral_modifiers)
        if isinstance(db_val, str) and db_val.startswith("["):
            db_val = safe_parse_json_array(db_val) or db_val

        if operator == "contains":
            if isinstance(db_val, list):
                result = value in db_val or (
                    isinstance(value, str) and
                    value.lower() in [str(v).lower() for v in db_val]
                )
                return result, f"{field_name} contains '{value}': {result}"
            if isinstance(db_val, str):
                result = str(value).lower() in db_val.lower()
                return result, f"{field_name} contains '{value}': {result}"
            return False, f"{field_name} not iterable"

        if operator == "intersects":
            if isinstance(db_val, list) and isinstance(values, list):
                db_lower = {str(v).lower() for v in db_val}
                val_lower = {str(v).lower() for v in values}
                result = bool(db_lower & val_lower)
                return result, f"{field_name} intersects {values}: {result}"
            return False, f"{field_name} not a list"

        if operator == "in":
            if isinstance(values, list):
                result = db_val in values or (
                    isinstance(db_val, str) and
                    db_val.lower() in [str(v).lower() for v in values]
                )
                return result, f"{field_name} in {values}: {result}"
            return False, "No values list for 'in' operator"

        # Numeric / string comparison
        try:
            if isinstance(value, (int, float)) and db_val is not None:
                db_num = float(db_val)
                result = _compare(db_num, operator, float(value))
                return result, f"{field_name} = {db_num} {operator} {value}: {result}"
        except (ValueError, TypeError):
            pass

        # String comparison
        result = _compare(db_val, operator, value)
        return result, f"{field_name} {operator} {value}: {result}"

    def _eval_signal(
        self,
        signal_name: str,
        operator: str,
        value: float,
        signals: dict[str, float],
    ) -> tuple[bool, str]:
        """Compare signal score against threshold."""
        score = signals.get(signal_name, 0.0)
        result = _compare(score, operator, value)
        return result, f"signal.{signal_name} = {score:.2f} {operator} {value}: {result}"


def _compare(a, op: str, b) -> bool:
    """Generic comparison operator."""
    if a is None:
        return False
    try:
        if op == "==":
            return a == b
        elif op == "!=":
            return a != b
        elif op == "<":
            return a < b
        elif op == ">":
            return a > b
        elif op == "<=":
            return a <= b
        elif op == ">=":
            return a >= b
    except TypeError:
        return False
    return False
