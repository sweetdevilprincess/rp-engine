"""Branch management — CRUD, trust baseline snapshots, ancestry walking, checkpoints.

Uses copy-on-write branching:
- Branch creation: INSERT record + snapshot trust baselines (2 steps)
- Rewind: creates a new branch instead of deleting (append-only)
- State resolved lazily through ancestry graph
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from rp_engine.database import PRIORITY_EXCHANGE, Database
from rp_engine.models.branch import (
    BranchInfo,
    BranchListResponse,
    CheckpointInfo,
    CheckpointRestoreResponse,
)
from rp_engine.services.context_engine import trust_stage

logger = logging.getLogger(__name__)


class BranchManager:
    """Manages branch lifecycle, trust baseline snapshots, and checkpoints."""

    def __init__(self, db: Database, state_manager=None, resolver=None) -> None:
        self.db = db
        self.state_manager = state_manager
        self.resolver = resolver

    # ===================================================================
    # Branch CRUD
    # ===================================================================

    async def ensure_main_branch(self, rp_folder: str) -> None:
        """Create the 'main' branch for an RP folder if it doesn't exist."""
        now = datetime.now(UTC).isoformat()
        future = await self.db.enqueue_write(
            """INSERT OR IGNORE INTO branches (name, rp_folder, is_active, created_at)
               VALUES ('main', ?, TRUE, ?)""",
            [rp_folder, now],
            priority=PRIORITY_EXCHANGE,
        )
        await future

    async def get_active_branch(self, rp_folder: str) -> str:
        """Get the active branch name for an RP folder. Defaults to 'main'."""
        row = await self.db.fetch_one(
            "SELECT name FROM branches WHERE rp_folder = ? AND is_active = TRUE",
            [rp_folder],
        )
        return row["name"] if row else "main"

    async def list_branches(self, rp_folder: str) -> BranchListResponse:
        """List all branches for an RP folder with exchange counts."""
        rows = await self.db.fetch_all(
            "SELECT * FROM branches WHERE rp_folder = ? ORDER BY created_at",
            [rp_folder],
        )

        active_branch = None
        branches: list[BranchInfo] = []
        for row in rows:
            count = await self.db.fetch_val(
                "SELECT COUNT(*) FROM exchanges WHERE rp_folder = ? AND branch = ?",
                [rp_folder, row["name"]],
            )
            info = BranchInfo(
                name=row["name"],
                rp_folder=rp_folder,
                created_from=row.get("created_from"),
                branch_point_session=row.get("branch_point_session"),
                branch_point_exchange=row.get("branch_point_exchange"),
                description=row.get("description"),
                is_active=bool(row.get("is_active")),
                created_at=row.get("created_at"),
                exchange_count=count or 0,
            )
            branches.append(info)
            if info.is_active:
                active_branch = info.name

        return BranchListResponse(active_branch=active_branch, branches=branches)

    async def get_branch(self, name: str, rp_folder: str) -> BranchInfo:
        """Get a single branch by name. Raises ValueError if not found."""
        row = await self.db.fetch_one(
            "SELECT * FROM branches WHERE name = ? AND rp_folder = ?",
            [name, rp_folder],
        )
        if not row:
            raise ValueError(f"Branch '{name}' not found in '{rp_folder}'")

        count = await self.db.fetch_val(
            "SELECT COUNT(*) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, name],
        )
        return BranchInfo(
            name=row["name"],
            rp_folder=rp_folder,
            created_from=row.get("created_from"),
            branch_point_session=row.get("branch_point_session"),
            branch_point_exchange=row.get("branch_point_exchange"),
            description=row.get("description"),
            is_active=bool(row.get("is_active")),
            created_at=row.get("created_at"),
            exchange_count=count or 0,
        )

    async def create_branch(
        self,
        name: str,
        rp_folder: str,
        description: str | None = None,
        branch_from: str | None = None,
    ) -> BranchInfo:
        """Create a new branch with trust baseline snapshots.

        CoW simplification (2 steps instead of 9):
        1. INSERT branch record
        2. Snapshot trust baselines from source branch
        Then activate the new branch.

        State (characters, scenes, events) is NOT copied — it's resolved
        lazily through the ancestry graph.
        """
        now = datetime.now(UTC).isoformat()

        # 1. Resolve source branch
        source = branch_from or await self.get_active_branch(rp_folder)
        source_row = await self.db.fetch_one(
            "SELECT * FROM branches WHERE name = ? AND rp_folder = ?",
            [source, rp_folder],
        )
        if not source_row:
            raise ValueError(f"Source branch '{source}' not found")

        # Check duplicate
        existing = await self.db.fetch_one(
            "SELECT 1 FROM branches WHERE name = ? AND rp_folder = ?",
            [name, rp_folder],
        )
        if existing:
            raise ValueError(f"Branch '{name}' already exists")

        # 2. Get branch point (latest exchange + active session on source)
        latest_exchange = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, source],
        )
        active_session = await self.db.fetch_one(
            """SELECT id FROM sessions WHERE rp_folder = ? AND branch = ?
               AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1""",
            [rp_folder, source],
        )
        session_id = active_session["id"] if active_session else None

        # 3. INSERT branch record
        future = await self.db.enqueue_write(
            """INSERT INTO branches (name, rp_folder, created_from, created_at,
                   branch_point_session, branch_point_exchange, description, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)""",
            [name, rp_folder, source, now, session_id, latest_exchange or 0, description],
            priority=PRIORITY_EXCHANGE,
        )
        await future

        # 4. Snapshot trust baselines from source
        await self._snapshot_trust_baselines(rp_folder, source, name, latest_exchange or 0, now)

        # 5. Copy thread_counters (lightweight, needed for plot tracking)
        counters = await self.db.fetch_all(
            "SELECT * FROM thread_counters WHERE rp_folder = ? AND branch = ?",
            [rp_folder, source],
        )
        for tc in counters:
            future = await self.db.enqueue_write(
                """INSERT INTO thread_counters (thread_id, rp_folder, branch, current_counter, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [tc["thread_id"], rp_folder, name, tc["current_counter"], now],
                priority=PRIORITY_EXCHANGE,
            )
            await future

        # 6. Activate the new branch + invalidate cache
        await self.switch_branch(name, rp_folder)
        if self.resolver:
            self.resolver.invalidate_cache(rp_folder)

        return await self.get_branch(name, rp_folder)

    async def _snapshot_trust_baselines(
        self, rp_folder: str, source_branch: str, new_branch: str,
        branch_point_exchange: int, now: str,
    ) -> None:
        """Snapshot accumulated trust from source branch into trust_baselines for new branch.

        Collects trust from:
        1. trust_baselines on source branch (if any)
        2. Plus SUM of trust_modifications on source branch
        3. Falls back to old relationships table if no baselines exist
        """
        # Try new system first: collect all trust modification pairs on source
        mod_pairs = await self.db.fetch_all(
            """SELECT character_a, character_b, SUM(change) as total_change
               FROM trust_modifications
               WHERE rp_folder = ? AND branch = ?
               GROUP BY character_a, character_b""",
            [rp_folder, source_branch],
        )

        # Get existing baselines on source
        source_baselines = await self.db.fetch_all(
            "SELECT * FROM trust_baselines WHERE rp_folder = ? AND branch = ?",
            [rp_folder, source_branch],
        )
        baseline_map: dict[tuple[str, str], int] = {}
        for sb in source_baselines:
            baseline_map[(sb["character_a"], sb["character_b"])] = sb.get("baseline_score") or 0

        # Build combined trust values
        all_pairs: dict[tuple[str, str], int] = {}

        # Start with baselines
        for pair, score in baseline_map.items():
            all_pairs[pair] = score

        # Add modifications
        for mp in mod_pairs:
            if mp["character_a"] and mp["character_b"]:
                pair = (mp["character_a"], mp["character_b"])
                all_pairs[pair] = all_pairs.get(pair, 0) + (mp["total_change"] or 0)

        # Also check old relationships table as fallback
        if not all_pairs:
            rel_rows = await self.db.fetch_all(
                "SELECT * FROM relationships WHERE rp_folder = ? AND branch = ?",
                [rp_folder, source_branch],
            )
            for rel in rel_rows:
                combined = (rel.get("initial_trust_score") or 0) + (rel.get("trust_modification_sum") or 0)
                pair = (rel["character_a"], rel["character_b"])
                all_pairs[pair] = combined

        # Insert baselines for the new branch
        for (char_a, char_b), score in all_pairs.items():
            future = await self.db.enqueue_write(
                """INSERT INTO trust_baselines
                       (character_a, character_b, rp_folder, branch, baseline_score,
                        baseline_stage, source_branch, source_exchange, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [char_a, char_b, rp_folder, new_branch, score,
                 trust_stage(score), source_branch, branch_point_exchange, now],
                priority=PRIORITY_EXCHANGE,
            )
            await future

    async def switch_branch(self, name: str, rp_folder: str) -> str:
        """Switch the active branch. Returns the previous active branch name."""
        previous = await self.get_active_branch(rp_folder)

        target = await self.db.fetch_one(
            "SELECT 1 FROM branches WHERE name = ? AND rp_folder = ?",
            [name, rp_folder],
        )
        if not target:
            raise ValueError(f"Branch '{name}' not found in '{rp_folder}'")

        future = await self.db.enqueue_write(
            "UPDATE branches SET is_active = FALSE WHERE rp_folder = ?",
            [rp_folder],
            priority=PRIORITY_EXCHANGE,
        )
        await future

        future = await self.db.enqueue_write(
            "UPDATE branches SET is_active = TRUE WHERE name = ? AND rp_folder = ?",
            [name, rp_folder],
            priority=PRIORITY_EXCHANGE,
        )
        await future

        if self.resolver:
            self.resolver.invalidate_cache(rp_folder)

        return previous

    # ===================================================================
    # Ancestry
    # ===================================================================

    async def get_exchanges_with_ancestry(
        self, rp_folder: str, branch: str, limit: int = 5, max_depth: int = 5
    ) -> list[dict]:
        """Get recent exchanges, walking to parent branches recursively."""
        rows = await self.db.fetch_all(
            """SELECT * FROM exchanges WHERE rp_folder = ? AND branch = ?
               ORDER BY exchange_number DESC LIMIT ?""",
            [rp_folder, branch, limit],
        )
        if len(rows) >= limit:
            return rows

        # Walk ancestry chain
        current = branch
        depth = 0
        while len(rows) < limit and depth < max_depth:
            branch_row = await self.db.fetch_one(
                "SELECT created_from, branch_point_exchange FROM branches WHERE name = ? AND rp_folder = ?",
                [current, rp_folder],
            )
            if not branch_row or not branch_row.get("created_from"):
                break

            parent = branch_row["created_from"]
            branch_point = branch_row["branch_point_exchange"] or 0
            remaining = limit - len(rows)

            parent_rows = await self.db.fetch_all(
                """SELECT * FROM exchanges WHERE rp_folder = ? AND branch = ?
                   AND exchange_number <= ? ORDER BY exchange_number DESC LIMIT ?""",
                [rp_folder, parent, branch_point, remaining],
            )
            rows = rows + parent_rows
            current = parent
            depth += 1

        return rows

    # ===================================================================
    # Checkpoints
    # ===================================================================

    async def create_checkpoint(
        self, name: str, rp_folder: str, branch: str, description: str | None = None
    ) -> CheckpointInfo:
        """Create a named checkpoint at the current exchange number."""
        now = datetime.now(UTC).isoformat()

        latest = await self.db.fetch_val(
            "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        if latest is None:
            raise ValueError("No exchanges to checkpoint")

        existing = await self.db.fetch_one(
            "SELECT 1 FROM checkpoints WHERE name = ? AND rp_folder = ? AND branch = ?",
            [name, rp_folder, branch],
        )
        if existing:
            raise ValueError(f"Checkpoint '{name}' already exists on branch '{branch}'")

        future = await self.db.enqueue_write(
            """INSERT INTO checkpoints (name, rp_folder, branch, exchange_number, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [name, rp_folder, branch, latest, description, now],
            priority=PRIORITY_EXCHANGE,
        )
        await future

        return CheckpointInfo(
            name=name,
            branch=branch,
            exchange_number=latest,
            description=description,
            created_at=now,
        )

    async def list_checkpoints(self, rp_folder: str, branch: str) -> list[CheckpointInfo]:
        """List all checkpoints for a branch."""
        rows = await self.db.fetch_all(
            "SELECT * FROM checkpoints WHERE rp_folder = ? AND branch = ? ORDER BY exchange_number",
            [rp_folder, branch],
        )
        return [
            CheckpointInfo(
                name=row["name"],
                branch=row["branch"],
                exchange_number=row["exchange_number"],
                description=row.get("description"),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def restore_checkpoint(
        self, checkpoint_name: str, rp_folder: str, branch: str
    ) -> CheckpointRestoreResponse:
        """Restore to a checkpoint by creating a new branch from that point.

        Append-only: never deletes data. The old timeline remains intact.
        Returns the new branch name.
        """
        cp = await self.db.fetch_one(
            "SELECT * FROM checkpoints WHERE name = ? AND rp_folder = ? AND branch = ?",
            [checkpoint_name, rp_folder, branch],
        )
        if not cp:
            raise ValueError(f"Checkpoint '{checkpoint_name}' not found on branch '{branch}'")

        target_exchange = cp["exchange_number"]

        # Generate a unique branch name for the rewind
        new_branch_name = f"{branch}-rewind-{target_exchange}"
        counter = 1
        while True:
            existing = await self.db.fetch_one(
                "SELECT 1 FROM branches WHERE name = ? AND rp_folder = ?",
                [new_branch_name, rp_folder],
            )
            if not existing:
                break
            counter += 1
            new_branch_name = f"{branch}-rewind-{target_exchange}-{counter}"

        now = datetime.now(UTC).isoformat()

        # Create new branch from the checkpoint's exchange point
        future = await self.db.enqueue_write(
            """INSERT INTO branches (name, rp_folder, created_from, created_at,
                   branch_point_session, branch_point_exchange, description, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)""",
            [new_branch_name, rp_folder, branch, now,
             cp.get("branch_point_session"), target_exchange,
             f"Rewind from checkpoint '{checkpoint_name}'"],
            priority=PRIORITY_EXCHANGE,
        )
        await future

        # Snapshot trust baselines at that point
        await self._snapshot_trust_baselines(
            rp_folder, branch, new_branch_name, target_exchange, now
        )

        # Copy thread counters
        counters = await self.db.fetch_all(
            "SELECT * FROM thread_counters WHERE rp_folder = ? AND branch = ?",
            [rp_folder, branch],
        )
        for tc in counters:
            future = await self.db.enqueue_write(
                """INSERT INTO thread_counters (thread_id, rp_folder, branch, current_counter, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [tc["thread_id"], rp_folder, new_branch_name, tc["current_counter"], now],
                priority=PRIORITY_EXCHANGE,
            )
            await future

        # Activate the new branch
        await self.switch_branch(new_branch_name, rp_folder)

        return CheckpointRestoreResponse(
            restored_from=checkpoint_name,
            exchange_number=target_exchange,
            new_branch=new_branch_name,
        )
