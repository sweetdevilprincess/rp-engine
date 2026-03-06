"""Context engine — the main intelligence orchestrator.

Accepts raw text, runs the 5-stage pipeline, returns everything an LLM
needs to produce the next response. Replaces 8 separate hooks with one
smart endpoint. "Smart API, dumb client."
"""

from __future__ import annotations

import asyncio
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
    ExtractedMemoryHit,
    FlaggedNPC,
    NPCBrief,
    PastExchangeHit,
    SceneState,
    StalenessWarning,
    ThreadAlert,
    TriggeredNote,
    WritingConstraints,
)
from rp_engine.models.rp import GuidelinesResponse
from rp_engine.services.entity_extractor import EntityExtractor
from rp_engine.services.graph_resolver import GraphResolver
from rp_engine.services.guidelines_service import GuidelinesService
from rp_engine.services.npc_brief_builder import NPCBriefBuilder
from rp_engine.services.scene_classifier import SceneClassifier
from rp_engine.services.trigger_evaluator import TriggerEvaluator
from rp_engine.services.vector_search import VectorSearch
from rp_engine.utils.json_helpers import safe_parse_json, safe_parse_json_list
from rp_engine.utils.text import hash_content as _hash_content
from rp_engine.utils.trust import TRUST_STAGES, trust_stage

logger = logging.getLogger(__name__)

# Importance levels that get full NPC briefs
BRIEF_IMPORTANCE = {"critical", "main", "antagonist", "love_interest"}


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
        guidelines_service: GuidelinesService | None = None,
        npc_brief_builder: NPCBriefBuilder | None = None,
        npc_engine: Any | None = None,
        lance_store: Any | None = None,
    ) -> None:
        self.db = db
        self.entity_extractor = entity_extractor
        self.scene_classifier = scene_classifier
        self.graph_resolver = graph_resolver
        self.vector_search = vector_search
        self.trigger_evaluator = trigger_evaluator
        self.config = config
        self.vault_root = vault_root
        self.guidelines_service = guidelines_service or GuidelinesService(vault_root)
        self.npc_brief_builder = npc_brief_builder or NPCBriefBuilder()
        self.npc_engine = npc_engine
        self.lance_store = lance_store
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
            past_exchanges,
            extracted_memories,
        ) = await asyncio.gather(
            self._keyword_match(extraction.matched_entities, rp_folder),
            self._semantic_search(request.user_message, rp_folder),
            self._get_scene_state(rp_folder, branch),
            self._get_character_states(rp_folder, branch),
            self._get_guidelines(rp_folder),
            self._get_thread_alerts(rp_folder, branch),
            self._get_card_gaps(rp_folder, branch),
            self._get_always_load_cards(rp_folder),
            self._get_writing_constraints(request.user_message, last_response),
            self._search_past_exchanges(
                request.user_message, rp_folder, branch, current_turn, session_id
            ),
            self._get_extracted_memories(
                request.user_message, rp_folder, branch,
                [n.name for n in extraction.active_npcs],
            ),
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
        trust_map: dict[tuple[str, str], int] = {}  # (char_a_lower, char_b_lower) -> trust score

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
                pair = (ca, cb)
                if ca in npc_names_lower or cb in npc_names_lower:
                    trust_map[pair] = trust_map.get(pair, 0) + row["baseline_score"]

            mod_rows = await self.db.fetch_all(
                """SELECT LOWER(character_a) as ca, LOWER(character_b) as cb,
                          COALESCE(SUM(change), 0) as total
                   FROM trust_modifications WHERE rp_folder = ? AND branch = ?
                   GROUP BY LOWER(character_a), LOWER(character_b)""",
                [rp_folder, branch],
            )
            for row in mod_rows:
                ca, cb = row["ca"], row["cb"]
                pair = (ca, cb)
                if ca in npc_names_lower or cb in npc_names_lower:
                    trust_map[pair] = trust_map.get(pair, 0) + row["total"]

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
                # Sum trust from all pairs involving this NPC
                npc_lower = npc.name.lower()
                pre_trust = sum(
                    score for (ca, cb), score in trust_map.items()
                    if ca == npc_lower or cb == npc_lower
                )
                brief = self.npc_brief_builder.build_brief(
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
            past_exchanges=past_exchanges,
            extracted_memories=extracted_memories,
            warnings=warnings,
            writing_constraints=writing_constraints,
        )

    async def get_continuity_brief(self, rp_folder: str, branch: str) -> dict:
        """Data-only continuity brief: scene, characters, recent exchanges, threads."""
        scene = await self.db.fetch_one(
            """SELECT location, time_of_day, mood, in_story_timestamp
               FROM scene_state_entries WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT 1""",
            [rp_folder, branch],
        )

        characters = await self.db.fetch_all(
            """SELECT sc.name,
                      cse.location, cse.emotional_state, cse.conditions
               FROM character_ledger cl
               JOIN story_cards sc ON cl.card_id = sc.id
               LEFT JOIN character_state_entries cse ON (
                   cse.card_id = cl.card_id AND cse.rp_folder = cl.rp_folder AND cse.branch = cl.branch
                   AND cse.exchange_number = (
                       SELECT MAX(exchange_number) FROM character_state_entries
                       WHERE card_id = cl.card_id AND rp_folder = cl.rp_folder AND branch = cl.branch
                   )
               )
               WHERE cl.rp_folder = ? AND cl.branch = ? AND cl.status = 'active'""",
            [rp_folder, branch],
        )

        exchanges = await self.db.fetch_all(
            """SELECT exchange_number, user_message, assistant_response, in_story_timestamp
               FROM exchanges WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT 3""",
            [rp_folder, branch],
        )

        threads = await self.db.fetch_all(
            """SELECT pt.name, pt.status, pt.phase, COALESCE(tc.current_counter, 0) as counter
               FROM plot_threads pt
               LEFT JOIN thread_counters tc ON pt.id = tc.thread_id AND pt.rp_folder = tc.rp_folder AND tc.branch = ?
               WHERE pt.rp_folder = ? AND pt.status = 'active'""",
            [branch, rp_folder],
        )

        return {
            "scene": dict(scene) if scene else None,
            "characters": [dict(c) for c in characters],
            "recent_exchanges": [dict(e) for e in exchanges],
            "active_threads": [dict(t) for t in threads],
        }

    # ===================================================================
    # Helper methods
    # ===================================================================

    async def _search_past_exchanges(
        self,
        user_message: str,
        rp_folder: str,
        branch: str,
        current_exchange: int,
        session_id: str | None,
    ) -> list[PastExchangeHit]:
        """Search LanceDB for relevant past exchange chunks."""
        if not self.lance_store:
            return []

        try:
            results = await self.lance_store.search_exchanges(
                query_text=user_message,
                rp_folder=rp_folder,
                branch=branch,
                limit=self.config.max_past_exchanges * 2,
                max_exchange=current_exchange,
            )
        except Exception as e:
            logger.warning("Past exchange search failed: %s", e)
            return []

        # Filter and deduplicate
        exclude_threshold = current_exchange - self.config.exclude_recent_exchanges
        seen_exchanges: dict[int, PastExchangeHit] = {}

        for r in results:
            ex_num = r.metadata.get("exchange_number", 0)

            # Skip recent exchanges already in context window
            if ex_num >= exclude_threshold:
                continue

            # Skip results from current session that are very recent
            r_session = r.metadata.get("session_id")
            if session_id and r_session == session_id and ex_num >= current_exchange - 5:
                continue

            # Score threshold
            if r.score < self.config.past_exchange_min_score:
                continue

            # Keep highest-scoring chunk per exchange
            if ex_num not in seen_exchanges or r.score > seen_exchanges[ex_num].score:
                seen_exchanges[ex_num] = PastExchangeHit(
                    exchange_number=ex_num,
                    session_id=r_session,
                    speaker=r.metadata.get("speaker", "unknown"),
                    text=r.text,
                    score=r.score,
                    in_story_timestamp=r.metadata.get("in_story_timestamp"),
                )

        # Return top N sorted by score
        hits = sorted(seen_exchanges.values(), key=lambda h: h.score, reverse=True)
        return hits[: self.config.max_past_exchanges]

    async def _get_extracted_memories(
        self,
        user_message: str,
        rp_folder: str,
        branch: str,
        active_npc_names: list[str],
    ) -> list[ExtractedMemoryHit]:
        """Load relevant extracted memories from the analysis pipeline."""
        try:
            rows = await self.db.fetch_all(
                """SELECT em.description, em.significance, em.characters,
                          em.in_story_timestamp, e.exchange_number
                   FROM extracted_memories em
                   LEFT JOIN exchanges e ON em.exchange_id = e.id
                   WHERE em.rp_folder = ? AND em.branch = ?
                   ORDER BY em.id DESC
                   LIMIT ?""",
                [rp_folder, branch, self.config.max_extracted_memories * 3],
            )
        except Exception as e:
            logger.warning("Extracted memories query failed: %s", e)
            return []

        if not rows:
            return []

        # Score memories by relevance to current context
        msg_lower = user_message.lower()
        msg_words = set(msg_lower.split())
        npc_names_lower = {n.lower() for n in active_npc_names}

        scored: list[tuple[float, dict]] = []
        for row in rows:
            desc = (row.get("description") or "").lower()
            characters_raw = row.get("characters") or "[]"
            characters = safe_parse_json_list(characters_raw)
            char_names_lower = {c.lower() for c in characters if c}

            # Score: keyword overlap + NPC mention bonus
            desc_words = set(desc.split())
            overlap = len(msg_words & desc_words)
            score = overlap / max(len(msg_words), 1)

            # Boost if memory mentions active NPCs
            if npc_names_lower & char_names_lower:
                score += 0.3

            if score >= self.config.extracted_memory_min_score:
                scored.append((score, row, characters))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            ExtractedMemoryHit(
                description=row.get("description", ""),
                significance=row.get("significance"),
                characters=chars,
                exchange_number=row.get("exchange_number"),
                in_story_timestamp=row.get("in_story_timestamp"),
            )
            for _, row, chars in scored[: self.config.max_extracted_memories]
        ]

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

        entity_ids = [m.entity_id for m in matched_entities]
        placeholders = ",".join("?" for _ in entity_ids)
        return await self.db.fetch_all(
            f"SELECT id, name, card_type, file_path, content, summary, content_hash FROM story_cards WHERE id IN ({placeholders})",
            entity_ids,
        )

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
        """Load all character states from CoW tables (batch query)."""
        # Get active characters from ledger
        ledger_rows = await self.db.fetch_all(
            """SELECT cl.card_id, sc.name
               FROM character_ledger cl
               JOIN story_cards sc ON cl.card_id = sc.id
               WHERE cl.rp_folder = ? AND cl.branch = ? AND cl.status = 'active'""",
            [rp_folder, branch],
        )
        if not ledger_rows:
            return {}

        card_ids = [lr["card_id"] for lr in ledger_rows]
        placeholders = ",".join("?" for _ in card_ids)

        # Batch fetch latest runtime state per card_id
        runtime_rows = await self.db.fetch_all(
            f"""SELECT cse.card_id, cse.location, cse.conditions, cse.emotional_state
                FROM character_state_entries cse
                INNER JOIN (
                    SELECT card_id, MAX(exchange_number) as max_ex
                    FROM character_state_entries
                    WHERE rp_folder = ? AND branch = ? AND card_id IN ({placeholders})
                    GROUP BY card_id
                ) latest ON cse.card_id = latest.card_id AND cse.exchange_number = latest.max_ex
                WHERE cse.rp_folder = ? AND cse.branch = ?""",
            [rp_folder, branch] + card_ids + [rp_folder, branch],
        )
        runtime_map = {row["card_id"]: row for row in runtime_rows}

        states: dict[str, CharacterState] = {}
        for lr in ledger_rows:
            runtime = runtime_map.get(lr["card_id"])
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
        """Load RP guidelines via GuidelinesService."""
        return self.guidelines_service.get_guidelines(rp_folder)

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

                # Pull evidence snippets for near-threshold threads
                evidence_snippets: list[str] = []
                try:
                    evidence_rows = await self.db.fetch_all(
                        """SELECT chunk_text FROM thread_evidence
                           WHERE thread_id = ? AND rp_folder = ? AND branch = ?
                             AND chunk_text IS NOT NULL
                           ORDER BY exchange_number DESC LIMIT 5""",
                        [thread["id"], rp_folder, branch],
                    )
                    evidence_snippets = [
                        r["chunk_text"] for r in evidence_rows if r["chunk_text"]
                    ]
                except Exception:
                    pass

                alerts.append(ThreadAlert(
                    thread_id=thread["id"],
                    name=thread["name"],
                    level=best_level,
                    counter=counter,
                    threshold=best_threshold,
                    consequence=consequence,
                    evidence_snippets=evidence_snippets,
                ))

        return alerts

    async def _get_card_gaps(self, rp_folder: str, branch: str = "main") -> list[CardGap]:
        """Load card gap tracking data."""
        rows = await self.db.fetch_all(
            "SELECT entity_name, seen_count, suggested_type FROM card_gaps WHERE rp_folder = ? AND branch = ? ORDER BY seen_count DESC LIMIT 10",
            [rp_folder, branch],
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
        """Load cards marked as always_load via indexed column."""
        return await self.db.fetch_all(
            """SELECT id, name, card_type, file_path, content, summary, content_hash, frontmatter
               FROM story_cards WHERE rp_folder = ? AND always_load = 1""",
            [rp_folder],
        )

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

