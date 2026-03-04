"""Base feedback processor — shared pattern extraction and matching logic.

Subclasses override:
- _build_extraction_prompt(): domain-specific LLM prompt
- _default_category(): fallback category string for heuristic extraction
- _parse_category(): validate and return a category string
- _create_category_enum(): construct category enum from string
"""

from __future__ import annotations

import json
import re
import uuid
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .db import BasePatternDB
from .types import CorrectionPair, Direction, ExtractionResult, FeedbackInput, Pattern

LLMCallable = Callable[[str], str]


class BaseFeedbackProcessor:
    """Shared feedback processing: extract patterns, match or create, update.

    Subclasses must set `_category_enum` and implement the abstract methods.
    """

    _category_enum: type[Enum]  # Set by subclass

    def __init__(self, db: BasePatternDB, llm_call: Optional[LLMCallable] = None):
        self.db = db
        self.llm_call = llm_call

    def process(self, feedback: FeedbackInput,
                signature: Any = None) -> list[str]:
        """Main entry point. Returns list of pattern IDs created/updated."""
        self.db.log_feedback(feedback, [])

        if self.llm_call:
            extractions = self._extract_patterns_with_llm(feedback, signature)
        else:
            extractions = self._extract_patterns_heuristic(feedback)

        pattern_ids = []
        for extraction in extractions:
            pid = self._match_or_create_pattern(extraction)
            pattern_ids.append(pid)

        return pattern_ids

    def _extract_patterns_with_llm(
        self, feedback: FeedbackInput, signature: Any
    ) -> list[ExtractionResult]:
        prompt = self._build_extraction_prompt(feedback, signature)
        response = self.llm_call(prompt)
        return self._parse_extraction_response(response)

    def _extract_patterns_heuristic(
        self, feedback: FeedbackInput
    ) -> list[ExtractionResult]:
        """Fallback when no LLM is available."""
        desc = (feedback.user_feedback or "Unprocessed feedback")[:200]
        rule = (feedback.user_feedback or "")[:100]
        return [ExtractionResult(
            category=self._default_category(),
            subcategory="general",
            description=desc,
            direction="avoid",
            compressed_rule=rule or desc[:100],
            context_triggers=[],
        )]

    def _parse_extraction_response(self, response: str) -> list[ExtractionResult]:
        """Defensive parsing of LLM response."""
        valid_categories = {c.value for c in self._category_enum}
        valid_directions = {d.value for d in Direction}
        fallback_category = self._default_category()

        parsed = None
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            pass

        if parsed is None:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if parsed is None:
            objects = re.findall(r'\{[^{}]+\}', response)
            if objects:
                parsed = []
                for obj_str in objects:
                    try:
                        parsed.append(json.loads(obj_str))
                    except json.JSONDecodeError:
                        continue

        if not parsed or not isinstance(parsed, list):
            return [ExtractionResult(
                category=fallback_category,
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
            category = item.get("category", fallback_category)
            if category not in valid_categories:
                category = fallback_category
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
                category=fallback_category,
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
            category=self._category_enum(extraction.category),
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

    # --- Subclass hooks ---

    @abstractmethod
    def _build_extraction_prompt(self, feedback: FeedbackInput, signature: Any) -> str:
        """Build domain-specific LLM extraction prompt."""
        ...

    @abstractmethod
    def _default_category(self) -> str:
        """Return the default fallback category string."""
        ...
