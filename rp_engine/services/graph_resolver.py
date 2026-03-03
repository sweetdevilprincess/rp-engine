"""BFS graph resolver for entity connections.

Traverses entity_connections to expand from seed entities outward,
following relationship edges bidirectionally. Returns connected
entities with hop distance and full path information.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field

from rp_engine.database import Database
from rp_engine.utils.normalization import (
    file_to_key,
    id_to_key,
    normalize_key,
    strip_parenthetical,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedConnection:
    entity_id: str
    entity_name: str
    card_type: str
    hop: int
    path: list[str]
    connection_type: str
    content: str | None = None
    summary: str | None = None


class GraphResolver:
    """Resolve entity connections via BFS graph traversal."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def resolve_entity(self, name: str, rp_folder: str) -> str | None:
        """Multi-pass entity resolution.

        Tries increasingly fuzzy strategies to find the entity_id.
        """
        prefix = f"{rp_folder}:"

        # Pass 1: Direct story_cards.id match
        key = normalize_key(name)
        candidate = f"{prefix}{key}"
        row = await self.db.fetch_one(
            "SELECT id FROM story_cards WHERE id = ?", [candidate]
        )
        if row:
            return row["id"]

        # Pass 2: entity_aliases lookup
        row = await self.db.fetch_one(
            """SELECT entity_id FROM entity_aliases
               WHERE alias = ? AND entity_id LIKE ?""",
            [key, f"{prefix}%"],
        )
        if row:
            return row["entity_id"]

        # Pass 3: Strip .md extension
        key_no_md = file_to_key(name)
        candidate = f"{prefix}{key_no_md}"
        row = await self.db.fetch_one(
            "SELECT id FROM story_cards WHERE id = ?", [candidate]
        )
        if row:
            return row["id"]

        # Pass 4: Underscores → spaces
        key_spaced = id_to_key(name)
        candidate = f"{prefix}{key_spaced}"
        row = await self.db.fetch_one(
            "SELECT id FROM story_cards WHERE id = ?", [candidate]
        )
        if row:
            return row["id"]

        # Pass 5: Strip parenthetical
        stripped = strip_parenthetical(name)
        if stripped != name:
            key_stripped = normalize_key(stripped)
            candidate = f"{prefix}{key_stripped}"
            row = await self.db.fetch_one(
                "SELECT id FROM story_cards WHERE id = ?", [candidate]
            )
            if row:
                return row["id"]

            # Also try alias with stripped name
            row = await self.db.fetch_one(
                """SELECT entity_id FROM entity_aliases
                   WHERE alias = ? AND entity_id LIKE ?""",
                [key_stripped, f"{prefix}%"],
            )
            if row:
                return row["entity_id"]

        return None

    async def get_connections(
        self,
        seed_ids: list[str],
        max_hops: int = 2,
        max_results: int = 15,
    ) -> list[ResolvedConnection]:
        """BFS from seed entities through entity_connections.

        Loads the full adjacency map for the RP in one query, then
        traverses in-memory. Seeds are NOT included in results.
        """
        if not seed_ids:
            return []

        # Determine rp_folder from first seed
        rp_folder = seed_ids[0].split(":")[0] if ":" in seed_ids[0] else None

        # Load entire adjacency list for RP
        adjacency = await self._load_adjacency(rp_folder)

        # BFS
        visited: set[str] = set(seed_ids)
        results: list[ResolvedConnection] = []
        queue: deque[tuple[str, int, list[str], str]] = deque()

        # Initialize queue with seed neighbors
        for seed in seed_ids:
            for neighbor, conn_type in adjacency.get(seed, []):
                if neighbor not in visited:
                    queue.append((neighbor, 1, [seed], conn_type))

        while queue and len(results) < max_results:
            entity_id, hop, path, conn_type = queue.popleft()

            if entity_id in visited:
                continue
            if hop > max_hops:
                continue

            visited.add(entity_id)

            # Look up card info
            card = await self.db.fetch_one(
                "SELECT id, name, card_type, content, summary FROM story_cards WHERE id = ?",
                [entity_id],
            )
            if not card:
                continue

            results.append(
                ResolvedConnection(
                    entity_id=entity_id,
                    entity_name=card["name"],
                    card_type=card["card_type"],
                    hop=hop,
                    path=path + [entity_id],
                    connection_type=conn_type,
                    content=card["content"] if hop == 1 else None,
                    summary=card.get("summary") if hop >= 2 else None,
                )
            )

            # Expand neighbors for next hop
            if hop < max_hops:
                for neighbor, next_conn_type in adjacency.get(entity_id, []):
                    if neighbor not in visited:
                        queue.append(
                            (neighbor, hop + 1, path + [entity_id], next_conn_type)
                        )

        return results

    async def get_npc_enrichment(
        self,
        npc_id: str,
        scene_ids: list[str],
        rp_folder: str,
        max_hops: int = 2,
    ) -> dict:
        """Gather memories, secrets, knowledge for an NPC via graph edges."""
        connections = await self.get_connections([npc_id], max_hops=max_hops)

        memories = []
        secrets = []
        knowledge = []

        for conn in connections:
            if conn.card_type == "memory":
                memories.append({
                    "entity_id": conn.entity_id,
                    "name": conn.entity_name,
                    "connection_type": conn.connection_type,
                    "content": conn.content,
                    "summary": conn.summary,
                })
            elif conn.card_type == "secret":
                secrets.append({
                    "entity_id": conn.entity_id,
                    "name": conn.entity_name,
                    "connection_type": conn.connection_type,
                    "content": conn.content,
                    "summary": conn.summary,
                })
            elif conn.card_type == "knowledge":
                knowledge.append({
                    "entity_id": conn.entity_id,
                    "name": conn.entity_name,
                    "connection_type": conn.connection_type,
                    "content": conn.content,
                    "summary": conn.summary,
                })

        return {
            "memories": memories,
            "secrets": secrets,
            "knowledge": knowledge,
        }

    async def filter_secrets_for_character(
        self, secret_ids: list[str], character_id: str
    ) -> list[str]:
        """POV-aware secret filtering.

        Keep secrets where known_by → character.
        Remove secrets where unknown_to → character.
        """
        if not secret_ids:
            return []

        kept: list[str] = []
        char_key = character_id.split(":")[-1] if ":" in character_id else character_id

        for sid in secret_ids:
            card = await self.db.fetch_one(
                "SELECT frontmatter FROM story_cards WHERE id = ?", [sid]
            )
            if not card or not card.get("frontmatter"):
                kept.append(sid)
                continue

            try:
                fm = json.loads(card["frontmatter"]) if isinstance(card["frontmatter"], str) else card["frontmatter"]
            except (json.JSONDecodeError, TypeError):
                kept.append(sid)
                continue

            # Check unknown_to
            unknown_to = fm.get("unknown_to", [])
            if isinstance(unknown_to, list):
                unknown_lower = [u.lower().strip() for u in unknown_to if isinstance(u, str)]
                if char_key.lower() in unknown_lower:
                    continue

            # Check known_by — if present, character must be listed
            known_by = fm.get("known_by", [])
            if isinstance(known_by, list) and known_by:
                known_lower = [
                    k.lower().strip().split("(")[0].strip()
                    for k in known_by if isinstance(k, str)
                ]
                if char_key.lower() not in known_lower:
                    continue

            kept.append(sid)

        return kept

    async def _load_adjacency(
        self, rp_folder: str | None
    ) -> dict[str, list[tuple[str, str]]]:
        """Load full adjacency list from entity_connections.

        Returns bidirectional edges: forward uses connection_type,
        reverse uses type + '_reverse'.
        """
        if rp_folder:
            # Load connections involving entities from this RP
            rows = await self.db.fetch_all(
                """SELECT ec.from_entity, ec.to_entity, ec.connection_type
                   FROM entity_connections ec
                   WHERE ec.from_entity LIKE ? OR ec.to_entity LIKE ?""",
                [f"{rp_folder}:%", f"{rp_folder}:%"],
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT from_entity, to_entity, connection_type FROM entity_connections"
            )

        adj: dict[str, list[tuple[str, str]]] = {}
        for row in rows:
            f, t, ct = row["from_entity"], row["to_entity"], row["connection_type"]
            adj.setdefault(f, []).append((t, ct))
            adj.setdefault(t, []).append((f, f"{ct}_reverse"))

        return adj
