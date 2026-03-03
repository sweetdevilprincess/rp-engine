"""Async analysis pipeline — orchestrates post-exchange state extraction.

After each exchange save, the pipeline:
1. Calls ResponseAnalyzer (LLM) to extract structured data
2. Updates character state via StateManager
3. Updates trust via StateManager
4. Adds events via StateManager
5. Records new entities in card_gaps table
6. Runs ThreadTracker counter updates
7. Runs TimestampTracker time advancement
8. Marks exchange analysis_status as completed
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from rp_engine.config import TrustConfig
from rp_engine.database import PRIORITY_ANALYSIS, Database
from rp_engine.models.analysis import AnalysisResult
from rp_engine.models.state import CharacterUpdate, SceneUpdate
from rp_engine.services.response_analyzer import ResponseAnalyzer
from rp_engine.services.state_manager import StateManager
from rp_engine.services.thread_tracker import ThreadTracker
from rp_engine.services.timestamp_tracker import TimestampTracker

logger = logging.getLogger(__name__)

# Trust change type mapping
TRUST_CHANGE_TYPES = {"trust_increase", "trust_decrease"}


class AnalysisPipeline:
    """Async pipeline that processes exchanges sequentially."""

    def __init__(
        self,
        db: Database,
        response_analyzer: ResponseAnalyzer,
        state_manager: StateManager,
        thread_tracker: ThreadTracker,
        timestamp_tracker: TimestampTracker,
        trust_config: TrustConfig,
    ) -> None:
        self.db = db
        self.response_analyzer = response_analyzer
        self.state_manager = state_manager
        self.thread_tracker = thread_tracker
        self.timestamp_tracker = timestamp_tracker
        self.trust_config = trust_config
        self._queue: asyncio.Queue[tuple[int, str, str]] = asyncio.Queue()
        self._consumer_task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the consumer loop."""
        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("Analysis pipeline started")

    async def stop(self) -> None:
        """Stop the consumer loop, drain remaining items."""
        if not self._running:
            return
        self._running = False
        # Put sentinel to wake consumer
        await self._queue.put((-1, "__STOP__", ""))
        if self._consumer_task:
            await self._consumer_task
        logger.info("Analysis pipeline stopped")

    async def enqueue(
        self, exchange_id: int, rp_folder: str, branch: str = "main"
    ) -> None:
        """Enqueue an exchange for analysis."""
        await self._queue.put((exchange_id, rp_folder, branch))
        logger.info("Enqueued exchange %d for analysis", exchange_id)

    async def _consumer_loop(self) -> None:
        """Process exchanges sequentially."""
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            exchange_id, rp_folder, branch = item
            if rp_folder == "__STOP__":
                # Drain remaining
                while not self._queue.empty():
                    try:
                        item = self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    eid, rpf, br = item
                    if rpf == "__STOP__":
                        continue
                    await self._process_with_retry(eid, rpf, br)
                break

            await self._process_with_retry(exchange_id, rp_folder, branch)

    async def _process_with_retry(
        self, exchange_id: int, rp_folder: str, branch: str
    ) -> None:
        """Process with exponential backoff retry (2s, 4s, 8s)."""
        delays = [2, 4, 8]
        for attempt in range(len(delays) + 1):
            try:
                result = await self._process_exchange(exchange_id, rp_folder, branch)
                logger.info(
                    "Analysis complete for exchange %d: %d chars updated, %d trust, %d events",
                    exchange_id,
                    result.characters_updated,
                    result.trust_changes,
                    result.events_added,
                )
                return
            except Exception as e:
                if attempt < len(delays):
                    delay = delays[attempt]
                    logger.warning(
                        "Analysis attempt %d failed for exchange %d, retrying in %ds: %s",
                        attempt + 1, exchange_id, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Analysis permanently failed for exchange %d: %s",
                        exchange_id, e,
                    )
                    # Mark as failed
                    await self.db.enqueue_write(
                        "UPDATE exchanges SET analysis_status = 'failed' WHERE id = ?",
                        [exchange_id],
                        priority=PRIORITY_ANALYSIS,
                    )

    async def _process_exchange(
        self, exchange_id: int, rp_folder: str, branch: str
    ) -> AnalysisResult:
        """Process a single exchange through the full pipeline."""
        # 1. Load exchange
        exchange = await self.db.fetch_one(
            "SELECT * FROM exchanges WHERE id = ?", [exchange_id]
        )
        if not exchange:
            raise ValueError(f"Exchange {exchange_id} not found")

        user_msg = exchange["user_message"]
        asst_resp = exchange["assistant_response"]

        # 2. Call ResponseAnalyzer (LLM)
        analysis = await self.response_analyzer.analyze(
            exchange_id, user_msg, asst_resp, rp_folder, branch
        )

        result = AnalysisResult(exchange_id=exchange_id)

        # 3. Apply character state updates
        for char_name, char_state in analysis.story_state.characters.items():
            updates = CharacterUpdate(
                location=char_state.location if char_state.location else None,
                conditions=char_state.conditions if char_state.conditions else None,
                emotional_state=char_state.emotional_state if char_state.emotional_state else None,
            )
            await self.state_manager.update_character(
                char_name, updates, rp_folder, branch, exchange_id=exchange_id
            )
            result.characters_updated += 1

        # 4. Apply scene context updates
        sc = analysis.story_state.scene_context
        if sc.location or sc.time_of_day or sc.mood:
            await self.state_manager.update_scene(
                SceneUpdate(
                    location=sc.location or None,
                    time_of_day=sc.time_of_day or None,
                    mood=sc.mood or None,
                ),
                rp_folder,
                branch,
                exchange_id=exchange_id,
            )

        # 5. Apply trust changes from relationship dynamics
        for rd in analysis.relationship_dynamics:
            if len(rd.characters) < 2:
                continue
            char_a, char_b = rd.characters[0], rd.characters[1]

            if rd.change_type == "trust_increase":
                await self.state_manager.update_trust(
                    char_a, char_b,
                    change=self.trust_config.increase_value,
                    direction="increase",
                    reason=rd.evidence,
                    rp_folder=rp_folder,
                    branch=branch,
                    exchange_id=exchange_id,
                )
                result.trust_changes += 1
            elif rd.change_type == "trust_decrease":
                await self.state_manager.update_trust(
                    char_a, char_b,
                    change=-self.trust_config.decrease_value,
                    direction="decrease",
                    reason=rd.evidence,
                    rp_folder=rp_folder,
                    branch=branch,
                    exchange_id=exchange_id,
                )
                result.trust_changes += 1
            else:
                # Other types (conflict_introduced, etc.) → event only
                await self.state_manager.add_event(
                    event=f"{rd.change_type}: {rd.evidence}",
                    characters=rd.characters,
                    significance="medium",
                    rp_folder=rp_folder,
                    branch=branch,
                    exchange_id=exchange_id,
                )
                result.events_added += 1

        # 6. Add significant events
        for ev in analysis.story_state.significant_events:
            await self.state_manager.add_event(
                event=ev.event,
                characters=ev.characters,
                significance=ev.significance,
                rp_folder=rp_folder,
                branch=branch,
                exchange_id=exchange_id,
            )
            result.events_added += 1

        # 7. Record new entities in card_gaps
        now = datetime.now(timezone.utc).isoformat()
        for char in analysis.new_entities.characters:
            if char.name:
                await self._upsert_card_gap(char.name, "character", rp_folder, now)
                result.card_gaps_added += 1
        for loc in analysis.new_entities.locations:
            if loc.name:
                await self._upsert_card_gap(loc.name, "location", rp_folder, now)
                result.card_gaps_added += 1
        for concept in analysis.new_entities.concepts:
            if concept.name:
                await self._upsert_card_gap(concept.name, "lore", rp_folder, now)
                result.card_gaps_added += 1

        # 8. Thread counter updates
        alerts = await self.thread_tracker.update_counters(
            asst_resp, rp_folder, branch, exchange_id
        )
        result.thread_alerts = len(alerts)

        # 9. Timestamp advancement
        ts_result = await self.timestamp_tracker.advance_time(
            asst_resp, rp_folder, branch
        )
        result.timestamp_advanced = ts_result.new_timestamp is not None

        # 10. Mark analysis as completed
        await self.db.enqueue_write(
            "UPDATE exchanges SET analysis_status = 'completed' WHERE id = ?",
            [exchange_id],
            priority=PRIORITY_ANALYSIS,
        )

        result.status = "completed"
        return result

    async def _upsert_card_gap(
        self, entity_name: str, suggested_type: str, rp_folder: str, now: str
    ) -> None:
        """Insert or increment seen_count for a card gap."""
        await self.db.enqueue_write(
            """INSERT INTO card_gaps (entity_name, rp_folder, suggested_type, seen_count, first_seen, last_seen)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(entity_name, rp_folder)
               DO UPDATE SET seen_count = seen_count + 1, last_seen = excluded.last_seen""",
            [entity_name, rp_folder, suggested_type, now, now],
            priority=PRIORITY_ANALYSIS,
        )
