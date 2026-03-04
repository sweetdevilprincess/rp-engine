"""Ancestry resolution for copy-on-write branching.

Resolves state by walking the branch ancestry graph. Each branch has a parent
(created_from) and a branch_point_exchange. The ancestry chain goes from the
current branch up to "main" (root).

Resolution algorithm for CoW tables (character_state_entries, scene_state_entries):
  for each (branch, max_exchange) in ancestry chain:
      query table WHERE branch=? AND exchange_number <= max_exchange
      ORDER BY exchange_number DESC LIMIT 1
      if found -> return
  return None (or card default)

Trust shortcut (no full ancestry walk needed):
  baseline = trust_baselines[char_a, char_b, branch] or card initial
  mods = SUM(trust_modifications WHERE char_a, char_b, branch)
  return baseline + mods
"""

from __future__ import annotations

import logging

from rp_engine.database import Database

logger = logging.getLogger(__name__)


class AncestryResolver:
    """Resolves state through the branch ancestry graph."""

    def __init__(self, db: Database) -> None:
        self.db = db
        # Cache: (rp_folder, branch) -> [(branch, max_exchange), ...]
        self._ancestry_cache: dict[tuple[str, str], list[tuple[str, int]]] = {}

    # ===================================================================
    # Ancestry Chain
    # ===================================================================

    async def get_ancestry_chain(
        self, rp_folder: str, branch: str
    ) -> list[tuple[str, int]]:
        """Get the ancestry chain from current branch to root.

        Returns list of (branch_name, max_exchange_number) tuples.
        The first entry is the current branch (max_exchange = infinity/very large).
        Each subsequent entry is a parent with max_exchange = branch_point_exchange.
        """
        cache_key = (rp_folder, branch)
        if cache_key in self._ancestry_cache:
            return self._ancestry_cache[cache_key]

        chain: list[tuple[str, int]] = []
        current = branch
        visited: set[str] = set()

        while current and current not in visited:
            visited.add(current)

            # Current branch has no upper limit on exchange_number
            if current == branch:
                chain.append((current, 2**31))  # effectively unlimited
            else:
                # Parent branches are capped at the branch_point_exchange
                # already added by the previous iteration
                pass

            # Look up parent
            row = await self.db.fetch_one(
                "SELECT created_from, branch_point_exchange FROM branches WHERE name = ? AND rp_folder = ?",
                [current, rp_folder],
            )
            if not row or not row.get("created_from"):
                break

            parent = row["created_from"]
            branch_point = row.get("branch_point_exchange") or 0
            chain.append((parent, branch_point))
            current = parent

        self._ancestry_cache[cache_key] = chain
        return chain

    def invalidate_cache(self, rp_folder: str | None = None, branch: str | None = None) -> None:
        """Clear ancestry chain cache.

        If rp_folder/branch specified, only clear entries that include that branch.
        Otherwise, clear everything.
        """
        if rp_folder is None:
            self._ancestry_cache.clear()
            return

        keys_to_remove = [
            k for k in self._ancestry_cache
            if k[0] == rp_folder and (branch is None or k[1] == branch)
        ]
        for k in keys_to_remove:
            del self._ancestry_cache[k]

    # ===================================================================
    # Generic Resolution (single latest entry)
    # ===================================================================

    async def resolve_through_ancestry(
        self,
        table: str,
        rp_folder: str,
        branch: str,
        filters: dict[str, str | int] | None = None,
        exchange_number: int | None = None,
    ) -> dict | None:
        """Find the latest matching row by walking the ancestry chain.

        For CoW tables like character_state_entries and scene_state_entries.
        Returns the first matching row found (most recent in ancestry).
        """
        chain = await self.get_ancestry_chain(rp_folder, branch)

        for chain_branch, max_exchange in chain:
            # Cap the exchange_number if specified
            effective_max = min(max_exchange, exchange_number) if exchange_number else max_exchange

            where_parts = ["rp_folder = ?", "branch = ?", "exchange_number <= ?"]
            params: list = [rp_folder, chain_branch, effective_max]

            if filters:
                for col, val in filters.items():
                    where_parts.append(f"{col} = ?")
                    params.append(val)

            where_clause = " AND ".join(where_parts)
            row = await self.db.fetch_one(
                f"SELECT * FROM {table} WHERE {where_clause} ORDER BY exchange_number DESC LIMIT 1",
                params,
            )
            if row:
                return dict(row)

        return None

    # ===================================================================
    # Generic Collection (all matching entries from ancestry)
    # ===================================================================

    async def collect_from_ancestry(
        self,
        table: str,
        rp_folder: str,
        branch: str,
        filters: dict[str, str | int] | None = None,
        exchange_number: int | None = None,
        order_by: str = "exchange_number DESC",
        limit: int | None = None,
    ) -> list[dict]:
        """Collect ALL matching rows from the entire ancestry chain.

        For tables like memory_entries, knowledge_entries, secret_events
        where we want all accumulated data, not just the latest.
        """
        chain = await self.get_ancestry_chain(rp_folder, branch)
        results: list[dict] = []

        for chain_branch, max_exchange in chain:
            effective_max = min(max_exchange, exchange_number) if exchange_number else max_exchange

            where_parts = ["rp_folder = ?", "branch = ?", "exchange_number <= ?"]
            params: list = [rp_folder, chain_branch, effective_max]

            if filters:
                for col, val in filters.items():
                    where_parts.append(f"{col} = ?")
                    params.append(val)

            where_clause = " AND ".join(where_parts)
            rows = await self.db.fetch_all(
                f"SELECT * FROM {table} WHERE {where_clause} ORDER BY {order_by}",
                params,
            )
            results.extend(dict(r) for r in rows)

        # Sort combined results and apply limit
        # Parse exchange_number for sorting
        if "DESC" in order_by:
            results.sort(key=lambda r: r.get("exchange_number", 0), reverse=True)
        else:
            results.sort(key=lambda r: r.get("exchange_number", 0))

        if limit:
            results = results[:limit]

        return results

    # ===================================================================
    # Character State Resolution
    # ===================================================================

    async def resolve_character_state(
        self,
        card_id: str,
        rp_folder: str,
        branch: str,
        exchange_number: int | None = None,
    ) -> dict | None:
        """Resolve the latest character runtime state through ancestry.

        Returns the most recent character_state_entries row for this card_id
        that is visible from the given branch/exchange point.
        """
        return await self.resolve_through_ancestry(
            table="character_state_entries",
            rp_folder=rp_folder,
            branch=branch,
            filters={"card_id": card_id},
            exchange_number=exchange_number,
        )

    # ===================================================================
    # Scene State Resolution
    # ===================================================================

    async def resolve_scene_state(
        self,
        rp_folder: str,
        branch: str,
        exchange_number: int | None = None,
    ) -> dict | None:
        """Resolve the latest scene state through ancestry."""
        return await self.resolve_through_ancestry(
            table="scene_state_entries",
            rp_folder=rp_folder,
            branch=branch,
            exchange_number=exchange_number,
        )

    # ===================================================================
    # Trust Resolution
    # ===================================================================

    async def resolve_trust(
        self,
        char_a: str,
        char_b: str,
        rp_folder: str,
        branch: str,
    ) -> dict:
        """Resolve current trust between two characters.

        Uses the trust shortcut: baseline + SUM(modifications on current branch).
        No full ancestry walk needed for current value.

        Returns dict with: baseline_score, branch_modifications_sum, live_score,
        trust_stage, source_branch, source_exchange.
        """
        from rp_engine.services.context_engine import trust_stage

        # 1. Get baseline for this branch
        baseline_row = await self.db.fetch_one(
            """SELECT * FROM trust_baselines
               WHERE character_a = ? AND character_b = ? AND rp_folder = ? AND branch = ?""",
            [char_a, char_b, rp_folder, branch],
        )

        if baseline_row:
            baseline = baseline_row.get("baseline_score") or 0
            source_branch = baseline_row.get("source_branch")
            source_exchange = baseline_row.get("source_exchange")
        else:
            # No baseline — fall back to card's initial_trust_score
            card_row = await self.db.fetch_one(
                """SELECT frontmatter FROM story_cards
                   WHERE rp_folder = ? AND LOWER(name) = LOWER(?)
                     AND card_type IN ('character', 'npc')""",
                [rp_folder, char_a],
            )
            baseline = 0
            if card_row and card_row.get("frontmatter"):
                import json
                try:
                    fm = json.loads(card_row["frontmatter"])
                    # Check npc_trust_levels first, then initial_trust_score
                    trust_levels = fm.get("npc_trust_levels", {})
                    if isinstance(trust_levels, dict):
                        # Case-insensitive lookup
                        for key, val in trust_levels.items():
                            if key.lower() == char_b.lower():
                                baseline = val
                                break
                    if baseline == 0:
                        baseline = fm.get("initial_trust_score", 0)
                except (json.JSONDecodeError, TypeError):
                    pass
            source_branch = None
            source_exchange = None

        # 2. Sum modifications on THIS branch only
        mod_sum = await self.db.fetch_val(
            """SELECT COALESCE(SUM(change), 0) FROM trust_modifications
               WHERE character_a = ? AND character_b = ? AND rp_folder = ? AND branch = ?""",
            [char_a, char_b, rp_folder, branch],
        )
        mod_sum = mod_sum or 0

        live = baseline + mod_sum

        return {
            "baseline_score": baseline,
            "branch_modifications_sum": mod_sum,
            "live_score": live,
            "trust_stage": trust_stage(live),
            "source_branch": source_branch,
            "source_exchange": source_exchange,
        }

    async def resolve_trust_full_history(
        self,
        char_a: str,
        char_b: str,
        rp_folder: str,
        branch: str,
    ) -> list[dict]:
        """Get the full trust modification history through ancestry.

        Walks the ancestry chain to collect all trust modifications for this pair.
        """
        chain = await self.get_ancestry_chain(rp_folder, branch)
        all_mods: list[dict] = []

        for chain_branch, max_exchange in chain:
            rows = await self.db.fetch_all(
                """SELECT * FROM trust_modifications
                   WHERE character_a = ? AND character_b = ?
                     AND rp_folder = ? AND branch = ?
                     AND exchange_number <= ?
                   ORDER BY exchange_number DESC""",
                [char_a, char_b, rp_folder, chain_branch, max_exchange],
            )
            all_mods.extend(dict(r) for r in rows)

        return all_mods
