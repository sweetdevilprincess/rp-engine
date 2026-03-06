"""Recap builder — generates "Previously On..." recaps from current story state.

On session start, searches for the most relevant past moments relative to the
current story state and generates a narrative recap via LLM.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from rp_engine.database import Database
from rp_engine.services.lance_store import LanceStore
from rp_engine.services.llm_client import LLMClient
from rp_engine.services.state_manager import StateManager
from rp_engine.services.thread_tracker import ThreadTracker
from rp_engine.models.session import Recap

logger = logging.getLogger(__name__)

_WORD_LIMITS = {"quick": 100, "standard": 250, "detailed": 500}

_RECAP_PROMPT = """\
Generate a "Previously on..." recap for this RP. Write in past tense,
narrative style. Keep it to approximately {word_limit} words.

Priority: unresolved conflicts > character dynamics > plot threads > setting

{stored_summaries}

Current Story State:
{state_summary}

Active Threads:
{thread_summary}

Recent Trust Changes:
{trust_summary}

Key Past Moments:
{past_moments}
"""


class RecapBuilder:
    """Generates "Previously On..." recaps from current story state."""

    def __init__(
        self,
        db: Database,
        lance_store: LanceStore,
        llm_client: LLMClient,
        state_manager: StateManager,
        thread_tracker: ThreadTracker,
    ) -> None:
        self.db = db
        self.lance_store = lance_store
        self.llm_client = llm_client
        self.state_manager = state_manager
        self.thread_tracker = thread_tracker

    async def generate_recap(
        self,
        rp_folder: str,
        branch: str = "main",
        session_id: str | None = None,
        style: str = "standard",
    ) -> Recap:
        """Generate a narrative recap from current story state."""
        word_limit = _WORD_LIMITS.get(style, 250)

        # Check cache
        state_hash = await self._compute_state_hash(rp_folder, branch)
        cached = await self._get_cached_recap(rp_folder, branch, style, state_hash)
        if cached:
            return cached

        # Gather state
        state_summary = await self._get_state_summary(rp_folder, branch)
        thread_summary = await self._get_thread_summary(rp_folder, branch)
        trust_summary = await self._get_recent_trust_summary(rp_folder, branch)
        past_moments = await self._search_establishing_moments(rp_folder, branch)
        stored_summaries = await self._get_stored_summaries(rp_folder, branch)

        # Build prompt
        prompt = _RECAP_PROMPT.format(
            word_limit=word_limit,
            stored_summaries=stored_summaries,
            state_summary=state_summary,
            thread_summary=thread_summary,
            trust_summary=trust_summary,
            past_moments=past_moments,
        )

        # Generate via LLM
        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            model=self.llm_client.models.card_generation,
            temperature=0.5,
            max_tokens=word_limit * 3,
        )

        now = datetime.now(UTC).isoformat()
        recap = Recap(
            rp_folder=rp_folder,
            branch=branch,
            session_id=session_id,
            style=style,
            recap_text=response.content,
            generated_at=now,
        )

        # Cache
        await self._store_recap(recap, state_hash)
        return recap

    async def get_recap(
        self, rp_folder: str, branch: str = "main", style: str = "standard"
    ) -> Recap | None:
        """Retrieve the most recent cached recap."""
        row = await self.db.fetch_one(
            """SELECT * FROM session_recaps
               WHERE rp_folder = ? AND branch = ? AND style = ?
               ORDER BY generated_at DESC LIMIT 1""",
            [rp_folder, branch, style],
        )
        if not row:
            return None
        return Recap(
            rp_folder=row["rp_folder"],
            branch=row["branch"],
            session_id=row.get("session_id"),
            style=row["style"],
            recap_text=row["recap_text"],
            generated_at=row["generated_at"],
        )

    async def _compute_state_hash(self, rp_folder: str, branch: str) -> str:
        """Hash current state for cache invalidation."""
        latest_exchange = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        latest_trust = await self.db.fetch_val(
            """SELECT MAX(tm.created_at) FROM trust_modifications tm
               JOIN exchanges ex ON tm.exchange_id = ex.id
               WHERE ex.rp_folder = ? AND ex.branch = ?""",
            [rp_folder, branch],
        )
        raw = f"{latest_exchange}:{latest_trust}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _get_cached_recap(
        self, rp_folder: str, branch: str, style: str, state_hash: str
    ) -> Recap | None:
        """Check for a valid cached recap."""
        row = await self.db.fetch_one(
            """SELECT * FROM session_recaps
               WHERE rp_folder = ? AND branch = ? AND style = ? AND state_hash = ?
               ORDER BY generated_at DESC LIMIT 1""",
            [rp_folder, branch, style, state_hash],
        )
        if not row:
            return None
        return Recap(
            rp_folder=row["rp_folder"],
            branch=row["branch"],
            session_id=row.get("session_id"),
            style=row["style"],
            recap_text=row["recap_text"],
            generated_at=row["generated_at"],
        )

    async def _get_state_summary(self, rp_folder: str, branch: str) -> str:
        """Summarize current scene and character states."""
        parts: list[str] = []

        # Scene state
        scene = await self.db.fetch_one(
            """SELECT location, time_of_day, mood, in_story_timestamp
               FROM scene_state_entries
               WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT 1""",
            [rp_folder, branch],
        )
        if scene:
            loc = scene.get("location") or "unknown"
            tod = scene.get("time_of_day") or ""
            mood = scene.get("mood") or ""
            parts.append(f"Location: {loc}, Time: {tod}, Mood: {mood}")

        # Character states
        char_rows = await self.db.fetch_all(
            """SELECT character_name, location, emotional_state, conditions
               FROM character_state_entries
               WHERE rp_folder = ? AND branch = ?
               AND exchange_number = (
                   SELECT MAX(exchange_number) FROM character_state_entries
                   WHERE rp_folder = ? AND branch = ? AND character_name = character_state_entries.character_name
               )""",
            [rp_folder, branch, rp_folder, branch],
        )
        for row in char_rows:
            info = [row["character_name"]]
            if row.get("location"):
                info.append(f"at {row['location']}")
            if row.get("emotional_state"):
                info.append(f"feeling {row['emotional_state']}")
            if row.get("conditions"):
                info.append(f"conditions: {row['conditions']}")
            parts.append(" | ".join(info))

        return "\n".join(parts) if parts else "No state recorded yet."

    async def _get_thread_summary(self, rp_folder: str, branch: str) -> str:
        """Active thread summary."""
        rows = await self.db.fetch_all(
            """SELECT pt.name, tc.current_counter, pt.threshold, pt.consequences
               FROM thread_counters tc
               JOIN plot_threads pt ON tc.thread_id = pt.id AND tc.rp_folder = pt.rp_folder
               WHERE tc.rp_folder = ? AND tc.branch = ?""",
            [rp_folder, branch],
        )
        if not rows:
            return "No active threads."
        parts = []
        for r in rows:
            line = f"- {r['name']}: {r['current_counter']}/{r['threshold']}"
            if r.get("consequences"):
                line += f" (consequence: {r['consequences']})"
            parts.append(line)
        return "\n".join(parts)

    async def _get_recent_trust_summary(self, rp_folder: str, branch: str) -> str:
        """Recent trust changes across last 2 sessions."""
        rows = await self.db.fetch_all(
            """SELECT r.character_b, SUM(tm.change) as total, tm.reason
               FROM trust_modifications tm
               JOIN relationships r ON tm.relationship_id = r.id
               JOIN exchanges ex ON tm.exchange_id = ex.id
               WHERE ex.rp_folder = ? AND ex.branch = ?
               GROUP BY r.character_b
               ORDER BY ABS(SUM(tm.change)) DESC
               LIMIT 5""",
            [rp_folder, branch],
        )
        if not rows:
            return "No trust changes recorded."
        return "\n".join(
            f"- {r['character_b']}: {r['total']:+d}" for r in rows
        )

    async def _search_establishing_moments(self, rp_folder: str, branch: str) -> str:
        """Search for significant past exchanges that established current state."""
        # Get recent exchanges with events or trust changes
        rows = await self.db.fetch_all(
            """SELECT DISTINCT ex.exchange_number, ex.assistant_response
               FROM exchanges ex
               LEFT JOIN events e ON e.exchange_id = ex.id
               LEFT JOIN trust_modifications tm ON tm.exchange_id = ex.id
               WHERE ex.rp_folder = ? AND ex.branch = ?
                 AND (e.id IS NOT NULL OR tm.id IS NOT NULL)
               ORDER BY ex.exchange_number DESC
               LIMIT 5""",
            [rp_folder, branch],
        )
        if not rows:
            return "No past moments found."
        parts = []
        for r in rows:
            snippet = (r["assistant_response"] or "")[:300]
            parts.append(f"- Exchange {r['exchange_number']}: {snippet}")
        return "\n".join(parts)

    async def _get_stored_summaries(self, rp_folder: str, branch: str) -> str:
        """Get recent session summaries if available."""
        rows = await self.db.fetch_all(
            """SELECT narrative_summary FROM session_summaries
               WHERE rp_folder = ? AND branch = ?
               ORDER BY generated_at DESC LIMIT 3""",
            [rp_folder, branch],
        )
        if not rows:
            return ""
        parts = ["Previous Session Summaries:"]
        for r in rows:
            parts.append(r["narrative_summary"])
        return "\n\n".join(parts)

    async def _store_recap(self, recap: Recap, state_hash: str) -> None:
        """Store recap in the database."""
        future = await self.db.enqueue_write(
            """INSERT INTO session_recaps
               (rp_folder, branch, session_id, style, recap_text, state_hash, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                recap.rp_folder,
                recap.branch,
                recap.session_id,
                recap.style,
                recap.recap_text,
                state_hash,
                recap.generated_at,
            ],
        )
        await future
