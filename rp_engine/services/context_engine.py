"""Context engine — the main intelligence orchestrator.

Accepts raw text, runs the 5-stage pipeline, returns everything an LLM
needs to produce the next response. Replaces 8 separate hooks with one
smart endpoint. "Smart API, dumb client."
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rp_engine.config import ContextConfig
from rp_engine.database import PRIORITY_ANALYSIS, Database
from rp_engine.models.context import (
    CardGap,
    CharacterState,
    ContextDocument,
    ContextReference,
    ContextRequest,
    ContextResponse,
    FlaggedNPC,
    NPCBrief,
    SceneState,
    StalenessWarning,
    ThreadAlert,
    TriggeredNote,
    WritingConstraints,
)
from rp_engine.models.rp import GuidelinesResponse
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.scene_classifier import SceneClassifier
from rp_engine.services.trigger_evaluator import TriggerEvaluator
from rp_engine.services.vector_search import VectorSearch
from rp_engine.utils.json_helpers import safe_parse_json, safe_parse_json_list

logger = logging.getLogger(__name__)

# Trust stage thresholds — expanded -50 to 50 range with 8 stages
TRUST_STAGES = [
    (-50, -36, "hostile"),
    (-35, -21, "antagonistic"),
    (-20, -11, "suspicious"),
    (-10,  -1, "wary"),
    (  0,   9, "neutral"),
    ( 10,  19, "familiar"),
    ( 20,  34, "trusted"),
    ( 35,  50, "devoted"),
]

# Source priority for ranking (higher = more relevant)
SOURCE_PRIORITY = {
    "always_load": 2.0,
    "keyword": 1.0,
    "trigger": 0.9,
    "semantic": 0.8,
}

# Importance levels that get full NPC briefs
BRIEF_IMPORTANCE = {"critical", "main", "antagonist", "love_interest"}


def trust_stage(score: int) -> str:
    """Compute trust stage from score in -50 to 50 range."""
    if score <= -36:
        return "hostile"
    if score <= -21:
        return "antagonistic"
    if score <= -11:
        return "suspicious"
    if score <= -1:
        return "wary"
    if score <= 9:
        return "neutral"
    if score <= 19:
        return "familiar"
    if score <= 34:
        return "trusted"
    return "devoted"


class ContextEngine:
    """Orchestrates the full context retrieval pipeline."""

    def __init__(
        self,
        db: Database,
        entity_extractor: EntityExtractor,
        scene_classifier: SceneClassifier,
        graph_resolver: GraphResolver,
        vector_search: VectorSearch,
        trigger_evaluator: TriggerEvaluator,
        config: ContextConfig,
        vault_root: Path,
        npc_engine: Any | None = None,
    ) -> None:
        self.db = db
        self.entity_extractor = entity_extractor
        self.scene_classifier = scene_classifier
        self.graph_resolver = graph_resolver
        self.vector_search = vector_search
        self.trigger_evaluator = trigger_evaluator
        self.config = config
        self.vault_root = vault_root
        self.npc_engine = npc_engine
        self.branch_manager = None
        self.writing_intelligence = None

    def configure(self, **kwargs: Any) -> None:
        """Set late-bound dependencies (avoids monkey-patching attributes)."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"ContextEngine has no attribute '{key}'")
            setattr(self, key, value)

    async def get_context(
        self,
        request: ContextRequest,
        rp_folder: str,
        branch: str = "main",
        session_id: str | None = None,
    ) -> ContextResponse:
        """The main 5-stage pipeline."""

        # Resolve last_response: prefer request field, fall back to DB
        last_response = request.last_response
        if last_response is None:
            last_response = await self._get_last_response(rp_folder, branch)

        # ---- Stage 1: Extraction + Classification (no LLM) ----
        extraction, signals = await asyncio.gather(
            self.entity_extractor.extract(
                request.user_message, last_response, rp_folder
            ),
            self.scene_classifier.classify(
                request.user_message, last_response, rp_folder, branch
            ),
        )

        # ---- Stage 2: Parallel Retrieval (no LLM) ----
        combined_text = request.user_message
        if last_response:
            combined_text = f"{last_response}\n{request.user_message}"

        current_turn = await self._get_current_exchange(rp_folder, branch)

        (
            keyword_cards,
            semantic_results,
            scene_state,
            char_states,
            guidelines,
            thread_alerts,
            card_gaps,
            always_load_cards,
            writing_constraints,
        ) = await asyncio.gather(
            self._keyword_match(extraction.matched_entities, rp_folder),
            self._semantic_search(request.user_message, rp_folder),
            self._get_scene_state(rp_folder, branch),
            self._get_character_states(rp_folder, branch),
            self._get_guidelines(rp_folder),
            self._get_thread_alerts(rp_folder, branch),
            self._get_card_gaps(rp_folder),
            self._get_always_load_cards(rp_folder),
            self._get_writing_constraints(request.user_message, last_response),
        )

        # ---- Stage 2.5: Trigger Evaluation (no LLM) ----
        fired_triggers = await self.trigger_evaluator.evaluate_all(
            rp_folder, branch, combined_text, signals, current_turn
        )

        triggered_notes: list[TriggeredNote] = []
        trigger_card_ids: list[str] = []
        for ft in fired_triggers:
            if ft.inject_type in ("context_note", "state_alert") and ft.inject_content:
                triggered_notes.append(TriggeredNote(
                    trigger_id=ft.trigger_id,
                    trigger_name=ft.trigger_name,
                    inject_type=ft.inject_type,
                    content=ft.inject_content,
                    priority=ft.priority,
                    signals_matched=ft.matched_conditions,
                ))
            elif ft.inject_type == "card_reference" and ft.inject_card_path:
                trigger_card_ids.append(ft.inject_card_path)

        # ---- Stage 3: Graph Expansion + Ranking ----
        # Merge all card sources
        all_cards: dict[str, tuple[dict, str, float]] = {}  # entity_id → (card, source, score)

        # Always-load cards
        for card in always_load_cards:
            all_cards[card["id"]] = (card, "always_load", 2.0)

        # Keyword matches
        for card in keyword_cards:
            eid = card["id"]
            if eid not in all_cards or all_cards[eid][2] < 1.0:
                all_cards[eid] = (card, "keyword", 1.0)

        # Semantic results
        for sr in semantic_results:
            # Look up entity by file_path
            card = await self.db.fetch_one(
                "SELECT id, name, card_type, file_path, content, summary, content_hash FROM story_cards WHERE file_path = ?",
                [sr.file_path],
            )
            if card and card["id"] not in all_cards:
                all_cards[card["id"]] = (card, "semantic", 0.8)

        # Trigger card references
        for card_path in trigger_card_ids:
            card = await self.db.fetch_one(
                "SELECT id, name, card_type, file_path, content, summary, content_hash FROM story_cards WHERE file_path = ?",
                [card_path],
            )
            if card and card["id"] not in all_cards:
                all_cards[card["id"]] = (card, "trigger", 0.9)

        # Graph expansion from matched entities
        seed_ids = [m.entity_id for m in extraction.matched_entities]
        if seed_ids:
            graph_connections = await self.graph_resolver.get_connections(
                seed_ids, max_hops=self.config.max_graph_hops
            )
            for conn in graph_connections:
                if conn.entity_id not in all_cards:
                    graph_score = 0.6 if conn.hop == 1 else 0.3
                    card = await self.db.fetch_one(
                        "SELECT id, name, card_type, file_path, content, summary, content_hash FROM story_cards WHERE id = ?",
                        [conn.entity_id],
                    )
                    if card:
                        all_cards[conn.entity_id] = (card, "graph", graph_score)

        # Rank and limit
        ranked = sorted(all_cards.items(), key=lambda x: x[1][2], reverse=True)
        top_cards = ranked[: self.config.max_documents]

        # ---- Stage 3.5: Context Sent Filtering ----
        documents: list[ContextDocument] = []
        references: list[ContextReference] = []

        for entity_id, (card, source, score) in top_cards:
            content_hash = card.get("content_hash") or _hash_content(card.get("content", ""))
            sent_row = None
            if session_id:
                sent_row = await self.db.fetch_one(
                    "SELECT content_hash, sent_at_turn FROM context_sent WHERE session_id = ? AND entity_id = ?",
                    [session_id, entity_id],
                )

            if sent_row:
                old_hash = sent_row["content_hash"]
                sent_turn = sent_row["sent_at_turn"]

                if old_hash == content_hash and (current_turn - sent_turn) < self.config.stale_threshold_turns:
                    # Already sent, unchanged, within stale window → reference
                    references.append(ContextReference(
                        name=card["name"],
                        card_type=card["card_type"],
                        sent_at_turn=sent_turn,
                    ))
                    continue
                else:
                    status = "updated" if old_hash != content_hash else "new"
            else:
                status = "new"

            documents.append(ContextDocument(
                name=card["name"],
                card_type=card["card_type"],
                file_path=card.get("file_path", ""),
                source=source,
                relevance_score=score,
                content=card.get("content") if source != "graph" or score >= 0.6 else None,
                summary=card.get("summary") if source == "graph" and score < 0.6 else None,
                status=status,
            ))

            # Record sent (await to ensure committed before next read)
            if session_id:
                now = datetime.now(UTC).isoformat()
                future = await self.db.enqueue_write(
                    """INSERT OR REPLACE INTO context_sent
                           (session_id, entity_id, content_hash, sent_at_turn, sent_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    [session_id, entity_id, content_hash, current_turn, now],
                    priority=PRIORITY_ANALYSIS,
                )
                await future

        # ---- Stage 4: NPC Handling (no LLM in Phase 2) ----
        npc_briefs: list[NPCBrief] = []
        flagged_npcs: list[FlaggedNPC] = []
        signal_list = list(signals.keys())

        # All detected NPCs (active + referenced)
        all_npcs = {n.entity_id: n for n in extraction.active_npcs}
        for n in extraction.referenced_npcs:
            if n.entity_id not in all_npcs:
                all_npcs[n.entity_id] = n

        # Batch-fetch card data, runtime state, and trust for all detected NPCs
        npc_ids = list(all_npcs.keys())
        card_map: dict[str, dict] = {}
        runtime_map: dict[str, dict] = {}
        trust_map: dict[str, int] = {}  # npc name (lower) -> trust score

        if npc_ids:
            # Batch card data
            placeholders = ",".join("?" for _ in npc_ids)
            card_rows = await self.db.fetch_all(
                f"SELECT id, importance, frontmatter FROM story_cards WHERE id IN ({placeholders})",
                npc_ids,
            )
            for row in card_rows:
                card_map[row["id"]] = row

            # Batch runtime state (latest per card_id)
            runtime_rows = await self.db.fetch_all(
                f"""SELECT cse.card_id, cse.emotional_state, cse.conditions
                    FROM character_state_entries cse
                    INNER JOIN (
                        SELECT card_id, MAX(exchange_number) as max_ex
                        FROM character_state_entries
                        WHERE rp_folder = ? AND branch = ? AND card_id IN ({placeholders})
                        GROUP BY card_id
                    ) latest ON cse.card_id = latest.card_id AND cse.exchange_number = latest.max_ex
                    WHERE cse.rp_folder = ? AND cse.branch = ?""",
                [rp_folder, branch] + npc_ids + [rp_folder, branch],
            )
            for row in runtime_rows:
                runtime_map[row["card_id"]] = row

            # Batch trust: baselines + modification sums
            npc_names_lower = {npc.name.lower() for npc in all_npcs.values()}
            baseline_rows = await self.db.fetch_all(
                """SELECT LOWER(character_a) as ca, LOWER(character_b) as cb, baseline_score
                   FROM trust_baselines WHERE rp_folder = ? AND branch = ?""",
                [rp_folder, branch],
            )
            for row in baseline_rows:
                ca, cb = row["ca"], row["cb"]
                if ca in npc_names_lower:
                    trust_map[ca] = trust_map.get(ca, 0) + row["baseline_score"]
                if cb in npc_names_lower and cb != ca:
                    trust_map[cb] = trust_map.get(cb, 0) + row["baseline_score"]

            mod_rows = await self.db.fetch_all(
                """SELECT LOWER(character_a) as ca, LOWER(character_b) as cb,
                          COALESCE(SUM(change), 0) as total
                   FROM trust_modifications WHERE rp_folder = ? AND branch = ?
                   GROUP BY LOWER(character_a), LOWER(character_b)""",
                [rp_folder, branch],
            )
            for row in mod_rows:
                ca, cb = row["ca"], row["cb"]
                if ca in npc_names_lower:
                    trust_map[ca] = trust_map.get(ca, 0) + row["total"]
                if cb in npc_names_lower and cb != ca:
                    trust_map[cb] = trust_map.get(cb, 0) + row["total"]

        active_npc_ids = {n.entity_id for n in extraction.active_npcs}

        for npc_id, npc in all_npcs.items():
            sc_row = card_map.get(npc_id)
            card_fm = safe_parse_json(sc_row.get("frontmatter")) if sc_row else {}
            importance = (sc_row["importance"] if sc_row else None) or card_fm.get("importance")

            runtime = runtime_map.get(npc_id)

            char_row = {
                "importance": importance,
                "primary_archetype": card_fm.get("primary_archetype"),
                "secondary_archetype": card_fm.get("secondary_archetype"),
                "behavioral_modifiers": card_fm.get("behavioral_modifiers"),
                "emotional_state": runtime["emotional_state"] if runtime else None,
                "conditions": runtime["conditions"] if runtime else None,
            }

            if importance and importance in BRIEF_IMPORTANCE:
                pre_trust = trust_map.get(npc.name.lower(), 0)
                brief = self._build_npc_brief_sync(
                    npc.name, char_row, pre_trust, signal_list
                )
                npc_briefs.append(brief)
            else:
                reason = "active_in_scene" if npc_id in active_npc_ids else "mentioned"
                flagged_npcs.append(FlaggedNPC(
                    character=npc.name,
                    importance=importance,
                    reason=reason,
                ))

        # ---- Stage 4b: Background NPC Reactions (Phase 3) ----
        npc_reactions = []
        if self.npc_engine and request.include_npc_reactions and flagged_npcs:
            active_flagged = [f for f in flagged_npcs if f.reason == "active_in_scene"]
            if active_flagged:
                try:
                    npc_reactions = await self.npc_engine.get_batch_reactions(
                        npc_names=[f.character for f in active_flagged],
                        scene_prompt=request.user_message,
                        rp_folder=rp_folder,
                        branch=branch,
                    )
                except Exception as e:
                    logger.warning("Background NPC reactions failed: %s", e)

        # ---- Stage 5: Assembly ----
        warnings = await self._get_warnings(rp_folder, branch)

        return ContextResponse(
            current_exchange=current_turn,
            documents=documents,
            references=references,
            npc_briefs=npc_briefs,
            npc_reactions=npc_reactions,
            flagged_npcs=flagged_npcs,
            guidelines=guidelines,
            scene_state=scene_state,
            character_states=char_states,
            thread_alerts=thread_alerts,
            triggered_notes=triggered_notes,
            card_gaps=card_gaps,
            warnings=warnings,
            writing_constraints=writing_constraints,
        )

    # ===================================================================
    # Helper methods
    # ===================================================================

    async def _get_last_response(self, rp_folder: str, branch: str) -> str | None:
        """Get the most recent assistant response from exchanges."""
        row = await self.db.fetch_one(
            """SELECT assistant_response FROM exchanges
               WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT 1""",
            [rp_folder, branch],
        )
        if row:
            return row["assistant_response"]

        # Fall back to parent branch via ancestry
        if self.branch_manager:
            ancestry_rows = await self.branch_manager.get_exchanges_with_ancestry(
                rp_folder, branch, limit=1
            )
            if ancestry_rows:
                return ancestry_rows[0]["assistant_response"]
        return None

    async def _get_current_exchange(self, rp_folder: str, branch: str) -> int:
        """Get the current exchange number."""
        val = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        if val:
            return val

        # Fall back to parent branch via ancestry
        if self.branch_manager:
            ancestry_rows = await self.branch_manager.get_exchanges_with_ancestry(
                rp_folder, branch, limit=1
            )
            if ancestry_rows:
                return ancestry_rows[0]["exchange_number"]
        return 0

    async def _keyword_match(self, matched_entities, rp_folder: str) -> list[dict]:
        """Load full card data for keyword-matched entities."""
        if not matched_entities:
            return []

        cards = []
        for m in matched_entities:
            card = await self.db.fetch_one(
                "SELECT id, name, card_type, file_path, content, summary, content_hash FROM story_cards WHERE id = ?",
                [m.entity_id],
            )
            if card:
                cards.append(card)
        return cards

    async def _semantic_search(self, query: str, rp_folder: str):
        """Run vector search for semantic matches."""
        try:
            return await self.vector_search.search(query, rp_folder=rp_folder, limit=5)
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []

    async def _get_scene_state(self, rp_folder: str, branch: str) -> SceneState:
        """Load current scene context from CoW scene_state_entries."""
        row = await self.db.fetch_one(
            """SELECT location, time_of_day, mood, in_story_timestamp
               FROM scene_state_entries WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT 1""",
            [rp_folder, branch],
        )
        if row:
            return SceneState(**{k: row[k] for k in ["location", "time_of_day", "mood", "in_story_timestamp"]})
        return SceneState()

    async def _get_character_states(
        self, rp_folder: str, branch: str
    ) -> dict[str, CharacterState]:
        """Load all character states from CoW tables."""
        # Get active characters from ledger
        ledger_rows = await self.db.fetch_all(
            """SELECT cl.card_id, sc.name
               FROM character_ledger cl
               JOIN story_cards sc ON cl.card_id = sc.id
               WHERE cl.rp_folder = ? AND cl.branch = ? AND cl.status = 'active'""",
            [rp_folder, branch],
        )
        states: dict[str, CharacterState] = {}
        for lr in ledger_rows:
            runtime = await self.db.fetch_one(
                """SELECT location, conditions, emotional_state
                   FROM character_state_entries
                   WHERE card_id = ? AND rp_folder = ? AND branch = ?
                   ORDER BY exchange_number DESC LIMIT 1""",
                [lr["card_id"], rp_folder, branch],
            )
            if runtime:
                conditions = safe_parse_json_list(runtime.get("conditions"))
                states[lr["name"]] = CharacterState(
                    location=runtime.get("location"),
                    conditions=conditions,
                    emotional_state=runtime.get("emotional_state"),
                )
            else:
                states[lr["name"]] = CharacterState()
        return states

    async def _get_guidelines(self, rp_folder: str) -> GuidelinesResponse | None:
        """Load RP guidelines."""
        from rp_engine.utils.frontmatter import parse_file

        guidelines_path = self.vault_root / rp_folder / "RP State" / "Story_Guidelines.md"
        if not guidelines_path.exists():
            return None

        try:
            frontmatter, _ = parse_file(guidelines_path)
            if frontmatter:
                return GuidelinesResponse(
                    pov_mode=frontmatter.get("pov_mode"),
                    dual_characters=frontmatter.get("dual_characters", []),
                    narrative_voice=frontmatter.get("narrative_voice"),
                    tense=frontmatter.get("tense"),
                    tone=frontmatter.get("tone"),
                    scene_pacing=frontmatter.get("scene_pacing"),
                    integrate_user_narrative=frontmatter.get("integrate_user_narrative"),
                )
        except Exception as e:
            logger.warning("Failed to parse guidelines: %s", e)

        return None

    async def _get_writing_constraints(
        self, user_message: str, last_response: str | None
    ) -> WritingConstraints | None:
        """Get writing quality constraints from the writing intelligence system."""
        if not self.writing_intelligence:
            return None
        try:
            payload = self.writing_intelligence.prepare(
                prompt=user_message,
                preceding_content=last_response,
            )
            if not payload.patterns_included:
                return None
            sig = payload.task_signature
            task_desc = f"{sig.intensity.value}-intensity {sig.register.value}, {sig.position.value}"
            return WritingConstraints(
                text=payload.text,
                patterns_included=payload.patterns_included,
                task_context=task_desc,
                token_count=payload.token_count,
            )
        except Exception:
            logger.warning("Writing intelligence failed", exc_info=True)
            return None

    async def _get_thread_alerts(
        self, rp_folder: str, branch: str
    ) -> list[ThreadAlert]:
        """Check plot threads for threshold alerts."""
        threads = await self.db.fetch_all(
            """SELECT pt.id, pt.name, pt.thresholds, pt.consequences,
                      COALESCE(tc.current_counter, 0) as counter
               FROM plot_threads pt
               LEFT JOIN thread_counters tc
                   ON pt.id = tc.thread_id AND pt.rp_folder = tc.rp_folder AND tc.branch = ?
               WHERE pt.rp_folder = ? AND pt.status = 'active'""",
            [branch, rp_folder],
        )

        alerts: list[ThreadAlert] = []
        for thread in threads:
            counter = thread.get("counter", 0) or 0
            thresholds_raw = thread.get("thresholds")
            consequences_raw = thread.get("consequences")

            if not thresholds_raw:
                continue

            thresholds = safe_parse_json(thresholds_raw)
            if not thresholds:
                continue

            consequences = safe_parse_json(consequences_raw)

            # Find highest crossed threshold
            best_level = None
            best_threshold = 0
            for level in ("strong", "moderate", "gentle"):
                t = thresholds.get(level)
                if t is not None and counter >= t and t > best_threshold:
                    best_level = level
                    best_threshold = t

            if best_level:
                consequence = ""
                if isinstance(consequences, dict):
                    consequence = consequences.get(best_level, "")
                elif isinstance(consequences, str):
                    consequence = consequences

                alerts.append(ThreadAlert(
                    thread_id=thread["id"],
                    name=thread["name"],
                    level=best_level,
                    counter=counter,
                    threshold=best_threshold,
                    consequence=consequence,
                ))

        return alerts

    async def _get_card_gaps(self, rp_folder: str) -> list[CardGap]:
        """Load card gap tracking data."""
        rows = await self.db.fetch_all(
            "SELECT entity_name, seen_count, suggested_type FROM card_gaps WHERE rp_folder = ? ORDER BY seen_count DESC LIMIT 10",
            [rp_folder],
        )
        return [
            CardGap(
                entity_name=r["entity_name"],
                seen_count=r["seen_count"],
                suggested_type=r.get("suggested_type"),
            )
            for r in rows
        ]

    async def _get_always_load_cards(self, rp_folder: str) -> list[dict]:
        """Load cards marked as always_load in frontmatter."""
        rows = await self.db.fetch_all(
            """SELECT id, name, card_type, file_path, content, summary, content_hash, frontmatter
               FROM story_cards WHERE rp_folder = ?""",
            [rp_folder],
        )
        always_load = []
        for row in rows:
            fm_raw = row.get("frontmatter")
            if fm_raw:
                fm = safe_parse_json(fm_raw)
                if fm.get("always_load"):
                    always_load.append(row)
        return always_load

    def _build_npc_brief_sync(
        self,
        name: str,
        char_row: dict | None,
        pre_trust: int,
        signal_list: list[str],
    ) -> NPCBrief:
        """Build a behavioral brief using pre-fetched data (no DB queries)."""
        archetype = char_row.get("primary_archetype") if char_row else None
        secondary = char_row.get("secondary_archetype") if char_row else None
        modifiers_raw = char_row.get("behavioral_modifiers") if char_row else None
        emotional = char_row.get("emotional_state") if char_row else None
        conditions_raw = char_row.get("conditions") if char_row else None
        importance = char_row.get("importance") if char_row else None

        modifiers = safe_parse_json_list(modifiers_raw)
        conditions = safe_parse_json_list(conditions_raw)

        stage = trust_stage(pre_trust)

        direction = self._build_behavioral_direction(
            archetype, stage, modifiers, signal_list
        )

        return NPCBrief(
            character=name,
            importance=importance,
            archetype=archetype,
            secondary_archetype=secondary,
            behavioral_modifiers=modifiers if isinstance(modifiers, list) else [],
            trust_score=pre_trust,
            trust_stage=stage,
            emotional_state=emotional,
            conditions=conditions if isinstance(conditions, list) else [],
            behavioral_direction=direction,
            scene_signals=signal_list,
        )

    def _build_behavioral_direction(
        self,
        archetype: str | None,
        stage: str,
        modifiers: list[str],
        signals: list[str],
    ) -> str:
        """Build a deterministic behavioral direction string (no LLM)."""
        parts: list[str] = []

        if archetype:
            parts.append(f"Archetype: {archetype}")

        parts.append(f"Trust: {stage}")

        if modifiers:
            parts.append(f"Modifiers: {', '.join(modifiers)}")

        if signals:
            parts.append(f"Scene: {', '.join(signals)}")

        # Behavioral guidance based on trust stage
        guidance_map = {
            "hostile": "Actively opposes. May betray or sabotage.",
            "antagonistic": "Open opposition. Refuses cooperation.",
            "suspicious": "Withholds information. Questions motives.",
            "wary": "Cautious engagement. Minimal vulnerability.",
            "neutral": "No strong feelings. Transactional interactions.",
            "familiar": "Willing to help. Some warmth and openness.",
            "trusted": "Confides freely. Protects and invests in relationship.",
            "devoted": "Deep loyalty. Will sacrifice for this person.",
        }
        if stage in guidance_map:
            parts.append(f"Direction: {guidance_map[stage]}")

        return " | ".join(parts)

    async def _get_warnings(
        self, rp_folder: str, branch: str
    ) -> list[StalenessWarning]:
        """Check for stale/failed analysis."""
        rows = await self.db.fetch_all(
            """SELECT exchange_number, analysis_status, created_at
               FROM exchanges
               WHERE rp_folder = ? AND branch = ? AND analysis_status = 'failed'
               ORDER BY exchange_number DESC LIMIT 5""",
            [rp_folder, branch],
        )
        return [
            StalenessWarning(
                exchange=r["exchange_number"],
                failed_at=r.get("created_at", ""),
                stale_fields=["npcs_involved", "location", "emotional_state"],
            )
            for r in rows
        ]


def _hash_content(content: str) -> str:
    """Quick hash for content change detection."""
    return hashlib.sha256(content.encode()).hexdigest()
