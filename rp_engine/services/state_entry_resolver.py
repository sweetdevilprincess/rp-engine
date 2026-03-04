"""Generic resolver for CoW state entry tables.

Encapsulates the common copy-on-write operations shared by all entry tables:
character_state_entries, scene_state_entries, trust_modifications,
thread_counter_entries, etc.

Each table follows the same pattern:
- Rows keyed by (rp_folder, branch, exchange_number, ...entity_keys)
- "Latest" = MAX(exchange_number) per entity on a branch
- Rewind = DELETE WHERE exchange_number > target
- Branch snapshot = copy latest entries from source to target branch
"""

from __future__ import annotations

import logging
from typing import Any

from rp_engine.database import PRIORITY_EXCHANGE, Database

logger = logging.getLogger(__name__)


class StateEntryResolver:
    """Generic resolver for CoW state entry tables."""

    def __init__(
        self,
        db: Database,
        table: str,
        entity_key_columns: list[str] | None = None,
    ) -> None:
        self.db = db
        self.table = table
        self.entity_keys = entity_key_columns or []

    async def resolve_latest(
        self,
        rp_folder: str,
        branch: str,
        **entity_keys: Any,
    ) -> dict | None:
        """Get the latest entry for an entity on a branch.

        Usage:
            await resolver.resolve_latest("Mafia", "main", card_id="dante")
        """
        where_parts = ["rp_folder = ?", "branch = ?"]
        params: list[Any] = [rp_folder, branch]

        for col in self.entity_keys:
            if col in entity_keys:
                where_parts.append(f"{col} = ?")
                params.append(entity_keys[col])

        where_clause = " AND ".join(where_parts)
        return await self.db.fetch_one(
            f"SELECT * FROM {self.table} WHERE {where_clause} "
            f"ORDER BY exchange_number DESC LIMIT 1",
            params,
        )

    async def resolve_latest_batch(
        self,
        rp_folder: str,
        branch: str,
        entity_key_values: list[Any],
    ) -> dict[Any, dict]:
        """Batch resolve latest entries for multiple entities.

        Only works for tables with a single entity key column.
        Returns {entity_key_value: row_dict}.
        """
        if not self.entity_keys or len(self.entity_keys) != 1:
            raise ValueError("resolve_latest_batch requires exactly one entity key column")
        if not entity_key_values:
            return {}

        key_col = self.entity_keys[0]
        placeholders = ",".join("?" for _ in entity_key_values)

        rows = await self.db.fetch_all(
            f"""SELECT t.* FROM {self.table} t
                INNER JOIN (
                    SELECT {key_col}, MAX(exchange_number) as max_ex
                    FROM {self.table}
                    WHERE rp_folder = ? AND branch = ? AND {key_col} IN ({placeholders})
                    GROUP BY {key_col}
                ) latest ON t.{key_col} = latest.{key_col}
                    AND t.exchange_number = latest.max_ex
                WHERE t.rp_folder = ? AND t.branch = ?""",
            [rp_folder, branch] + list(entity_key_values) + [rp_folder, branch],
        )

        return {row[key_col]: dict(row) for row in rows}

    async def resolve_all_latest(
        self,
        rp_folder: str,
        branch: str,
    ) -> list[dict]:
        """Get latest entry per entity on a branch.

        For tables without entity keys, returns the single latest entry.
        """
        if not self.entity_keys:
            row = await self.db.fetch_one(
                f"SELECT * FROM {self.table} WHERE rp_folder = ? AND branch = ? "
                f"ORDER BY exchange_number DESC LIMIT 1",
                [rp_folder, branch],
            )
            return [dict(row)] if row else []

        key_cols = ", ".join(self.entity_keys)
        key_join = " AND ".join(
            f"t.{col} = latest.{col}" for col in self.entity_keys
        )

        rows = await self.db.fetch_all(
            f"""SELECT t.* FROM {self.table} t
                INNER JOIN (
                    SELECT {key_cols}, MAX(exchange_number) as max_ex
                    FROM {self.table}
                    WHERE rp_folder = ? AND branch = ?
                    GROUP BY {key_cols}
                ) latest ON {key_join} AND t.exchange_number = latest.max_ex
                WHERE t.rp_folder = ? AND t.branch = ?""",
            [rp_folder, branch, rp_folder, branch],
        )

        return [dict(row) for row in rows]

    async def rewind_after(
        self,
        exchange_number: int,
        rp_folder: str,
        branch: str,
    ) -> int:
        """Delete all entries after a given exchange number (for rewind).

        Returns the number of rows affected (via future result).
        """
        future = await self.db.enqueue_write(
            f"DELETE FROM {self.table} WHERE rp_folder = ? AND branch = ? "
            f"AND exchange_number > ?",
            [rp_folder, branch, exchange_number],
            priority=PRIORITY_EXCHANGE,
        )
        await future
        # Count remaining for verification
        count = await self.db.fetch_val(
            f"SELECT COUNT(*) FROM {self.table} WHERE rp_folder = ? AND branch = ? "
            f"AND exchange_number > ?",
            [rp_folder, branch, exchange_number],
        )
        return count or 0

    async def snapshot_to_branch(
        self,
        source_branch: str,
        target_branch: str,
        at_exchange: int,
        rp_folder: str,
    ) -> int:
        """Copy latest entries from source branch to target branch.

        For branch creation: snapshots current state as exchange 0 on new branch.
        Returns number of rows copied.
        """
        # Get all latest entries on source up to at_exchange
        if not self.entity_keys:
            row = await self.db.fetch_one(
                f"SELECT * FROM {self.table} WHERE rp_folder = ? AND branch = ? "
                f"AND exchange_number <= ? ORDER BY exchange_number DESC LIMIT 1",
                [rp_folder, source_branch, at_exchange],
            )
            rows = [dict(row)] if row else []
        else:
            key_cols = ", ".join(self.entity_keys)
            key_join = " AND ".join(
                f"t.{col} = latest.{col}" for col in self.entity_keys
            )

            rows = await self.db.fetch_all(
                f"""SELECT t.* FROM {self.table} t
                    INNER JOIN (
                        SELECT {key_cols}, MAX(exchange_number) as max_ex
                        FROM {self.table}
                        WHERE rp_folder = ? AND branch = ? AND exchange_number <= ?
                        GROUP BY {key_cols}
                    ) latest ON {key_join} AND t.exchange_number = latest.max_ex
                    WHERE t.rp_folder = ? AND t.branch = ?""",
                [rp_folder, source_branch, at_exchange, rp_folder, source_branch],
            )
            rows = [dict(row) for row in rows]

        if not rows:
            return 0

        # Insert each row with target_branch and exchange_number=0
        for row in rows:
            row = dict(row)
            # Remove auto-increment id if present
            row.pop("id", None)
            row["branch"] = target_branch
            row["exchange_number"] = 0

            columns = list(row.keys())
            placeholders = ", ".join("?" for _ in columns)
            col_names = ", ".join(columns)

            future = await self.db.enqueue_write(
                f"INSERT INTO {self.table} ({col_names}) VALUES ({placeholders})",
                list(row.values()),
                priority=PRIORITY_EXCHANGE,
            )
            await future

        return len(rows)
