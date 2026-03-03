import json
import re
import uuid
from datetime import datetime
from typing import Callable, Optional

from .types import (
    CorrectionPair, ExtractionResult, FeedbackInput, Pattern,
    PatternCategory, Direction, TaskSignature,
)
from .db import PatternDB

LLMCallable = Callable[[str], str]


class FeedbackProcessor:
    def __init__(self, db: PatternDB, llm_call: Optional[LLMCallable] = None):
        self.db = db
        self.llm_call = llm_call

    def process(self, feedback: FeedbackInput,
                task_signature: Optional[TaskSignature] = None) -> list[str]:
        """
        Main entry point. Returns list of pattern IDs created/updated.
        1. Log raw feedback
        2. Extract patterns (LLM or heuristic)
        3. Match or create each pattern
        4. Update feedback log with pattern IDs
        5. Return all pattern IDs
        """
        feedback_id = self.db.log_feedback(feedback, [])

        if self.llm_call:
            extractions = self._extract_patterns_with_llm(feedback, task_signature)
        else:
            extractions = self._extract_patterns_heuristic(feedback)

        pattern_ids = []
        for extraction in extractions:
            pid = self._match_or_create_pattern(extraction)
            pattern_ids.append(pid)

        return pattern_ids

    def _extract_patterns_with_llm(
        self, feedback: FeedbackInput,
        task_sig: Optional[TaskSignature]
    ) -> list[ExtractionResult]:
        prompt = self._build_extraction_prompt(feedback, task_sig)
        response = self.llm_call(prompt)
        return self._parse_extraction_response(response)

    def _extract_patterns_heuristic(
        self, feedback: FeedbackInput
    ) -> list[ExtractionResult]:
        """Fallback when no LLM is available."""
        desc = (feedback.user_feedback or "Unprocessed feedback")[:200]
        rule = (feedback.user_feedback or "")[:100]
        return [ExtractionResult(
            category="word_choice",
            subcategory="general",
            description=desc,
            direction="avoid",
            compressed_rule=rule or desc[:100],
            context_triggers=[],
        )]

    def _build_extraction_prompt(
        self, feedback: FeedbackInput,
        task_sig: Optional[TaskSignature]
    ) -> str:
        sig_desc = "Not provided"
        if task_sig:
            sig_desc = (f"Mode: {task_sig.mode.value}, Register: {task_sig.register.value}, "
                        f"Intensity: {task_sig.intensity.value}, Position: {task_sig.position.value}, "
                        f"Elements: {[e.value for e in task_sig.elements]}")

        return f"""You are a writing pattern analyzer. Given an original LLM output and a user's correction, extract distinct writing patterns that should be tracked.

ORIGINAL OUTPUT:
{feedback.original_output}

USER'S REWRITE:
{feedback.user_rewrite or "Not provided"}

USER'S FEEDBACK:
{feedback.user_feedback or "Not provided"}

SCENE CONTEXT:
{sig_desc}

For each pattern you identify, return a JSON array of objects with:
- "category": one of: figurative_language, narrative_distance, information_ordering, detail_selection, reader_trust, pacing, dialogue, word_choice, structure
- "subcategory": a specific subcategory string
- "description": what the pattern is (1-2 sentences)
- "direction": "avoid" or "prefer"
- "compressed_rule": the rule in under 30 words
- "context_triggers": list of applicable triggers from:
  Modes: drafting, continuing, revising, expanding, condensing
  Registers: action, dialogue, introspection, description, exposition, transition
  Intensity: high, medium, low
  Position: opening, rising, climax, falling, closing, mid
  Elements: physical_action, dialogue, internal_thought, environmental_description, character_description, emotional_beat, sensory_detail
- "original_excerpt": the specific passage from the original (if applicable)
- "revised_excerpt": the corresponding revised passage (if applicable)

Return ONLY a JSON array. No explanation outside the JSON."""

    def _parse_extraction_response(self, response: str) -> list[ExtractionResult]:
        """Defensive parsing of LLM response."""
        valid_categories = {c.value for c in PatternCategory}
        valid_directions = {d.value for d in Direction}

        parsed = None
        # Try direct parse
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array via regex
        if parsed is None:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        # Try to extract individual objects
        if parsed is None:
            objects = re.findall(r'\{[^{}]+\}', response)
            if objects:
                parsed = []
                for obj_str in objects:
                    try:
                        parsed.append(json.loads(obj_str))
                    except json.JSONDecodeError:
                        continue

        # All parsing failed
        if not parsed or not isinstance(parsed, list):
            return [ExtractionResult(
                category="word_choice",
                subcategory="general",
                description="LLM extraction failed: " + response[:200],
                direction="avoid",
                compressed_rule="Review original feedback manually",
                context_triggers=[],
            )]

        results = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            category = item.get("category", "word_choice")
            if category not in valid_categories:
                category = "word_choice"
            direction = item.get("direction", "avoid")
            if direction not in valid_directions:
                direction = "avoid"

            results.append(ExtractionResult(
                category=category,
                subcategory=item.get("subcategory"),
                description=item.get("description", "No description provided"),
                direction=direction,
                compressed_rule=item.get("compressed_rule", ""),
                context_triggers=item.get("context_triggers", []),
                original_excerpt=item.get("original_excerpt"),
                revised_excerpt=item.get("revised_excerpt"),
                critique_excerpt=item.get("critique_excerpt"),
            ))

        if not results:
            return [ExtractionResult(
                category="word_choice",
                subcategory="general",
                description="LLM extraction returned no valid patterns",
                direction="avoid",
                compressed_rule="Review original feedback manually",
                context_triggers=[],
            )]

        return results

    def _match_or_create_pattern(self, extraction: ExtractionResult) -> str:
        existing = self.db.find_pattern_by_category_subcategory(
            extraction.category, extraction.subcategory)
        if existing:
            self._update_existing_pattern(existing, extraction)
            return existing.id
        return self._create_new_pattern(extraction)

    def _update_existing_pattern(
        self, pattern: Pattern, extraction: ExtractionResult
    ) -> None:
        pattern.correction_count += 1
        pattern.severity = min(1.0, pattern.severity + 0.1)
        if pattern.proficiency > 0.5:
            pattern.proficiency = 0.3
        pattern.last_corrected = datetime.utcnow()
        # Merge context triggers
        existing_triggers = set(pattern.context_triggers)
        existing_triggers.update(extraction.context_triggers)
        pattern.context_triggers = list(existing_triggers)
        self.db.update_pattern(pattern)

        if extraction.original_excerpt and extraction.revised_excerpt:
            pair = CorrectionPair(
                id=str(uuid.uuid4()),
                pattern_id=pattern.id,
                original=extraction.original_excerpt,
                revised=extraction.revised_excerpt,
                critique=extraction.critique_excerpt,
                extracted_rule=extraction.compressed_rule,
                tokens_original=len(extraction.original_excerpt.split()),
                tokens_revised=len(extraction.revised_excerpt.split()),
                created_at=datetime.utcnow(),
            )
            self.db.insert_correction_pair(pair)

    def _create_new_pattern(self, extraction: ExtractionResult) -> str:
        pattern_id = str(uuid.uuid4())
        pattern = Pattern(
            id=pattern_id,
            category=PatternCategory(extraction.category),
            subcategory=extraction.subcategory,
            description=extraction.description,
            direction=Direction(extraction.direction),
            severity=0.5,
            proficiency=0.2,
            frequency=1,
            correction_count=1,
            context_triggers=extraction.context_triggers,
            compressed_rule=extraction.compressed_rule,
            last_corrected=datetime.utcnow(),
        )
        self.db.insert_pattern(pattern)

        if extraction.original_excerpt and extraction.revised_excerpt:
            pair = CorrectionPair(
                id=str(uuid.uuid4()),
                pattern_id=pattern_id,
                original=extraction.original_excerpt,
                revised=extraction.revised_excerpt,
                critique=extraction.critique_excerpt,
                extracted_rule=extraction.compressed_rule,
                tokens_original=len(extraction.original_excerpt.split()),
                tokens_revised=len(extraction.revised_excerpt.split()),
                created_at=datetime.utcnow(),
            )
            self.db.insert_correction_pair(pair)

        return pattern_id
