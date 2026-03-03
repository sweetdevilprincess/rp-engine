from typing import Callable, Optional

from .types import (
    FeedbackInput, InjectionPayload, Pattern, BehavioralSignature,
)
from .db import BehavioralPatternDB
from .classifier import BehavioralClassifier
from .retrieval import BehavioralRetriever
from .injection import BehavioralInjectionFormatter
from .feedback import BehavioralFeedbackProcessor
from .proficiency import ProficiencyUpdater


class NPCIntelligence:
    def __init__(self, db_path: str = "npc_intelligence.db",
                 token_budget: int = 500,
                 llm_call: Optional[Callable[[str], str]] = None,
                 count_tokens: Optional[Callable[[str], int]] = None):
        self.db = BehavioralPatternDB(db_path)
        self.classifier = BehavioralClassifier()
        self.retriever = BehavioralRetriever(self.db)
        self.formatter = BehavioralInjectionFormatter(token_budget, count_tokens)
        self.feedback_processor = BehavioralFeedbackProcessor(self.db, llm_call)
        self.proficiency_updater = ProficiencyUpdater(self.db)

        self._session_id: Optional[str] = None
        self._current_behavioral_sig: Optional[BehavioralSignature] = None
        self._current_injected_ids: list[str] = []
        self._current_output_id: Optional[str] = None
        self._exchange_count: int = 0

    def start_session(self) -> str:
        self._session_id = self.db.create_session()
        self._exchange_count = 0
        return self._session_id

    def end_session(self) -> dict:
        patterns = self.db.get_all_patterns()
        avg_prof = (sum(p.proficiency for p in patterns) / len(patterns)) if patterns else 0.0
        self.db.end_session(self._session_id, self._exchange_count,
                            len(patterns), avg_prof)
        summary = {
            "session_id": self._session_id,
            "exchanges": self._exchange_count,
            "patterns_active": len(patterns),
            "avg_proficiency": round(avg_prof, 3),
        }
        self._session_id = None
        return summary

    def prepare(self, npc_name: str, archetype: str = "common_people",
                modifiers: Optional[list[str]] = None,
                trust_stage: str = "neutral", trust_score: int = 0,
                scene_signals: Optional[dict[str, float]] = None,
                scene_prompt: str = "",
                override: Optional[dict] = None) -> InjectionPayload:
        behavioral_sig = self.classifier.classify(
            archetype=archetype,
            modifiers=modifiers,
            trust_stage=trust_stage,
            trust_score=trust_score,
            scene_signals=scene_signals,
            scene_prompt=scene_prompt,
            override=override,
        )
        scored = self.retriever.retrieve(behavioral_sig)
        payload = self.formatter.format(scored, behavioral_sig, npc_name)

        self._current_behavioral_sig = behavioral_sig
        self._current_injected_ids = payload.patterns_included

        self._current_output_id = self.db.log_output(
            self._session_id or "", behavioral_sig,
            payload.patterns_included, "")

        return payload

    def record_outcome(self, output_text: str, accepted: bool = True,
                       feedback: Optional[FeedbackInput] = None) -> dict:
        self._exchange_count += 1

        if accepted:
            if self._current_output_id:
                self.db.mark_output_accepted(self._current_output_id)
            self.proficiency_updater.on_accepted(self._current_injected_ids)
            result = {
                "output_id": self._current_output_id,
                "patterns_updated": list(self._current_injected_ids),
                "patterns_created": [],
            }
        elif feedback:
            if self._current_output_id:
                self.db.mark_output_corrected(self._current_output_id, [])

            pattern_ids = self.feedback_processor.process(
                feedback, self._current_behavioral_sig)

            corrected_and_injected = set(pattern_ids) & set(self._current_injected_ids)
            corrected_not_injected = set(pattern_ids) - set(self._current_injected_ids)

            self.proficiency_updater.on_corrected(
                list(corrected_and_injected), self._current_injected_ids)

            for pid in corrected_not_injected:
                self.proficiency_updater.on_regression(pid)

            if self._current_output_id:
                self.db.mark_output_corrected(self._current_output_id, pattern_ids)

            result = {
                "output_id": self._current_output_id,
                "patterns_updated": list(corrected_and_injected),
                "patterns_created": list(set(pattern_ids) - corrected_and_injected),
            }
        else:
            result = {
                "output_id": self._current_output_id,
                "patterns_updated": [],
                "patterns_created": [],
            }

        self._current_behavioral_sig = None
        self._current_injected_ids = []
        self._current_output_id = None
        return result

    # --- Direct Pattern Management ---

    def add_pattern(self, pattern: Pattern) -> str:
        return self.db.insert_pattern(pattern)

    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        return self.db.get_pattern(pattern_id)

    def list_patterns(self, category: Optional[str] = None) -> list[Pattern]:
        patterns = self.db.get_all_patterns()
        if category:
            patterns = [p for p in patterns if p.category.value == category]
        return patterns

    def update_pattern(self, pattern: Pattern) -> None:
        self.db.update_pattern(pattern)

    # --- Diagnostics ---

    def get_stats(self) -> dict:
        patterns = self.db.get_all_patterns()
        if not patterns:
            return {"total_patterns": 0, "avg_proficiency": 0.0,
                    "by_category": {}, "low_proficiency_count": 0,
                    "high_severity_count": 0}
        by_cat = {}
        for p in patterns:
            cat = p.category.value
            by_cat[cat] = by_cat.get(cat, 0) + 1
        return {
            "total_patterns": len(patterns),
            "avg_proficiency": round(
                sum(p.proficiency for p in patterns) / len(patterns), 3),
            "by_category": by_cat,
            "low_proficiency_count": sum(1 for p in patterns if p.proficiency < 0.4),
            "high_severity_count": sum(1 for p in patterns if p.severity > 0.7),
        }

    # --- Lifecycle ---

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
