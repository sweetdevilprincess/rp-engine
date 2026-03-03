"""Story card indexer — parses .md files, builds entity graph in SQLite.

Ported from .claude/scripts/lib/frontmatter-index.js.
Two-pass indexing: (1) build entity+alias maps, (2) extract connections.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from rp_engine.database import Database, PRIORITY_REINDEX
from rp_engine.utils.frontmatter import parse_file
from rp_engine.utils.normalization import (
    file_to_key,
    id_to_key,
    normalize_key,
    strip_parenthetical,
)

logger = logging.getLogger(__name__)

# Card type → subdirectory name under Story Cards/
CARD_TYPE_DIRS: dict[str, str] = {
    "character": "Characters",
    "npc": "NPCs",
    "location": "Locations",
    "secret": "Secrets",
    "memory": "Memories",
    "knowledge": "Knowledge",
    "organization": "Organizations",
    "plot_thread": "Plot Threads",
    "item": "Items",
    "lore": "Lore",
}

# Reverse: directory name → card type
DIR_TO_TYPE: dict[str, str] = {v.lower(): k for k, v in CARD_TYPE_DIRS.items()}

# Connection extraction rules: (card_type, frontmatter_field) → connection_type
CONNECTION_RULES: list[tuple[str, str, str]] = [
    # Characters
    ("character", "memories", "has_memory"),
    ("character", "knowledge_refs", "has_knowledge"),
    ("character", "relationships", "has_relationship"),
    ("character", "npc_trust_levels", "trusts"),
    # Memories
    ("memory", "belongs_to", "belongs_to"),
    ("memory", "characters_involved", "involves_character"),
    ("memory", "who_else_remembers", "shared_memory"),
    ("memory", "related_memories", "related_memory"),
    # Secrets
    ("secret", "known_by", "known_by"),
    ("secret", "belongs_to", "belongs_to"),
    ("secret", "connects_to_secrets", "connects_to_secret"),
    # Locations
    ("location", "connected_locations", "connects_to"),
    ("location", "secrets_hidden_here", "hides_secret"),
    ("location", "regular_occupants", "occupied_by"),
    ("location", "significant_events", "has_event"),
    # Organizations
    ("organization", "key_members", "has_member"),
    ("organization", "allies", "allied_with"),
    ("organization", "rivals", "rival_of"),
    ("organization", "headquarters", "headquartered_at"),
    # Plot threads
    ("plot_thread", "related_threads", "related_thread"),
    ("plot_thread", "related_characters", "involves_character"),
    ("plot_thread", "related_locations", "involves_location"),
    # Knowledge
    ("knowledge", "belongs_to", "belongs_to"),
    ("knowledge", "related_to", "related_to"),
    # Items
    ("item", "current_holder", "held_by"),
    ("item", "known_by", "known_by"),
]


class CardIndexer:
    """Indexes story card .md files into SQLite for fast entity/connection lookup."""

    def __init__(self, db: Database, vault_root: Path) -> None:
        self.db = db
        self.vault_root = vault_root

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def full_index(self, rp_folder: str) -> dict[str, int]:
        """Two-pass full index of all story cards in an RP folder.

        Returns counts: ``{entities, connections, aliases, keywords}``.
        """
        start = time.monotonic()
        story_cards_dir = self.vault_root / rp_folder / "Story Cards"
        if not story_cards_dir.is_dir():
            logger.warning("No Story Cards directory in %s", rp_folder)
            return {"entities": 0, "connections": 0, "aliases": 0, "keywords": 0}

        # Clear existing data for this RP folder
        await self._clear_rp(rp_folder)

        # Pass 1: Parse all files, build entity map + alias map
        entities: dict[str, dict[str, Any]] = {}  # entity_id → {data}
        alias_map: dict[str, str] = {}  # alias → entity_id

        md_files = list(story_cards_dir.rglob("*.md"))
        for file_path in md_files:
            frontmatter, body = parse_file(file_path)
            if frontmatter is None:
                continue

            rel_path = file_path.relative_to(self.vault_root)
            card_type = self._detect_type(frontmatter, rel_path)
            name = self._extract_name(frontmatter, file_path)
            if not name:
                continue

            entity_id = f"{rp_folder}:{normalize_key(name)}"
            content = file_path.read_text(encoding="utf-8")
            content_hash = self._compute_content_hash(content)

            entities[entity_id] = {
                "id": entity_id,
                "rp_folder": rp_folder,
                "file_path": str(rel_path).replace("\\", "/"),
                "card_type": card_type,
                "name": name,
                "importance": frontmatter.get("importance"),
                "summary": frontmatter.get("summary"),
                "frontmatter": frontmatter,
                "content": content,
                "content_hash": content_hash,
                "file_mtime": file_path.stat().st_mtime,
                "body": body,
            }

            # Build alias map
            aliases = self._extract_aliases(entity_id, frontmatter, file_path)
            for alias in aliases:
                alias_map[alias] = entity_id

        # Insert entities into DB
        import json

        for eid, data in entities.items():
            future = await self.db.enqueue_write(
                """INSERT OR REPLACE INTO story_cards
                   (id, rp_folder, file_path, card_type, name, importance, summary,
                    frontmatter, content, content_hash, file_mtime, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                [
                    data["id"], data["rp_folder"], data["file_path"],
                    data["card_type"], data["name"], data["importance"],
                    data["summary"], json.dumps(data["frontmatter"], default=str),
                    data["content"], data["content_hash"], data["file_mtime"],
                ],
                priority=PRIORITY_REINDEX,
            )
            await future

        # Insert aliases
        alias_count = 0
        for alias, eid in alias_map.items():
            future = await self.db.enqueue_write(
                "INSERT OR REPLACE INTO entity_aliases (alias, entity_id) VALUES (?, ?)",
                [alias, eid],
                priority=PRIORITY_REINDEX,
            )
            await future
            alias_count += 1

        # Insert keywords
        known_entities = set(entities.keys())
        keyword_count = 0
        for eid, data in entities.items():
            keywords = self._extract_keywords(eid, data["frontmatter"])
            for kw in keywords:
                future = await self.db.enqueue_write(
                    "INSERT OR REPLACE INTO entity_keywords (keyword, entity_id) VALUES (?, ?)",
                    [kw, eid],
                    priority=PRIORITY_REINDEX,
                )
                await future
                keyword_count += 1

        # Pass 2: Extract connections using complete maps
        # Build a simple entity key set for resolution
        entity_keys: dict[str, str] = {}  # normalized_key → entity_id
        for eid in entities:
            # entity_id is "rp_folder:normalized_key"
            key = eid.split(":", 1)[1] if ":" in eid else eid
            entity_keys[key] = eid

        connection_count = 0
        for eid, data in entities.items():
            connections = self._extract_connections(
                eid, data["frontmatter"], data["card_type"],
                entity_keys, alias_map, rp_folder,
            )
            for conn in connections:
                future = await self.db.enqueue_write(
                    """INSERT INTO entity_connections
                       (from_entity, to_entity, connection_type, field, role)
                       VALUES (?, ?, ?, ?, ?)""",
                    [conn["from"], conn["to"], conn["type"], conn.get("field"), conn.get("role")],
                    priority=PRIORITY_REINDEX,
                )
                await future
                connection_count += 1

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "Full index of %s: %d entities, %d connections, %d aliases, %d keywords (%.0fms)",
            rp_folder, len(entities), connection_count, alias_count, keyword_count, elapsed,
        )
        return {
            "entities": len(entities),
            "connections": connection_count,
            "aliases": alias_count,
            "keywords": keyword_count,
            "duration_ms": elapsed,
        }

    async def index_file(self, rp_folder: str, file_path: Path) -> bool:
        """Incrementally index a single file. Returns True if indexed."""
        if not file_path.exists() or not file_path.suffix == ".md":
            return False

        frontmatter, body = parse_file(file_path)
        if frontmatter is None:
            return False

        rel_path = file_path.relative_to(self.vault_root)
        card_type = self._detect_type(frontmatter, rel_path)
        name = self._extract_name(frontmatter, file_path)
        if not name:
            return False

        entity_id = f"{rp_folder}:{normalize_key(name)}"
        content = file_path.read_text(encoding="utf-8")
        content_hash = self._compute_content_hash(content)

        # Check if unchanged
        existing = await self.db.fetch_one(
            "SELECT content_hash FROM story_cards WHERE id = ?", [entity_id]
        )
        if existing and existing["content_hash"] == content_hash:
            return False  # No changes

        # Remove old data for this entity
        await self._remove_entity(entity_id)

        import json

        # Insert entity
        future = await self.db.enqueue_write(
            """INSERT OR REPLACE INTO story_cards
               (id, rp_folder, file_path, card_type, name, importance, summary,
                frontmatter, content, content_hash, file_mtime, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            [
                entity_id, rp_folder, str(rel_path).replace("\\", "/"),
                card_type, name, frontmatter.get("importance"),
                frontmatter.get("summary"), json.dumps(frontmatter),
                content, content_hash, file_path.stat().st_mtime,
            ],
            priority=PRIORITY_REINDEX,
        )
        await future

        # Aliases
        aliases = self._extract_aliases(entity_id, frontmatter, file_path)
        for alias in aliases:
            future = await self.db.enqueue_write(
                "INSERT OR REPLACE INTO entity_aliases (alias, entity_id) VALUES (?, ?)",
                [alias, entity_id],
                priority=PRIORITY_REINDEX,
            )
            await future

        # Keywords
        keywords = self._extract_keywords(entity_id, frontmatter)
        for kw in keywords:
            future = await self.db.enqueue_write(
                "INSERT OR REPLACE INTO entity_keywords (keyword, entity_id) VALUES (?, ?)",
                [kw, entity_id],
                priority=PRIORITY_REINDEX,
            )
            await future

        # Connections — load existing entities/aliases from DB for resolution
        entity_keys, alias_map_db = await self._load_resolution_maps(rp_folder)
        connections = self._extract_connections(
            entity_id, frontmatter, card_type,
            entity_keys, alias_map_db, rp_folder,
        )
        for conn in connections:
            future = await self.db.enqueue_write(
                """INSERT INTO entity_connections
                   (from_entity, to_entity, connection_type, field, role)
                   VALUES (?, ?, ?, ?, ?)""",
                [conn["from"], conn["to"], conn["type"], conn.get("field"), conn.get("role")],
                priority=PRIORITY_REINDEX,
            )
            await future

        logger.info("Indexed file: %s → %s", rel_path, entity_id)
        return True

    async def remove_file(self, rp_folder: str, file_path: Path) -> bool:
        """Remove a file's entity and all its connections/aliases/keywords."""
        rel_path = str(file_path.relative_to(self.vault_root)).replace("\\", "/")
        row = await self.db.fetch_one(
            "SELECT id FROM story_cards WHERE file_path = ?", [rel_path]
        )
        if not row:
            return False

        await self._remove_entity(row["id"])
        logger.info("Removed entity for deleted file: %s", rel_path)
        return True

    def get_all_rp_folders(self) -> list[str]:
        """Auto-discover RP folders by scanning vault_root for dirs with Story Cards/."""
        folders = []
        if not self.vault_root.is_dir():
            return folders
        for child in self.vault_root.iterdir():
            if child.is_dir() and (child / "Story Cards").is_dir():
                folders.append(child.name)
        return sorted(folders)

    # ------------------------------------------------------------------
    # Internal: Entity extraction
    # ------------------------------------------------------------------

    def _detect_type(self, frontmatter: dict, relative_path: Path) -> str:
        """Detect card type from frontmatter or directory path."""
        fm_type = frontmatter.get("type")
        if fm_type:
            t = normalize_key(str(fm_type))
            # Normalize common variants
            if t in ("plot_thread", "thread"):
                return "plot_thread"
            if t in CARD_TYPE_DIRS:
                return t
            # Check if it's a character in the NPCs directory
            if t == "character":
                path_str = str(relative_path).replace("\\", "/").lower()
                if "/npcs/" in path_str:
                    return "npc"
                return "character"
            return t

        # Fallback: infer from directory
        path_str = str(relative_path).replace("\\", "/").lower()
        for dir_name, card_type in DIR_TO_TYPE.items():
            if f"/{dir_name}/" in path_str or path_str.startswith(f"{dir_name}/"):
                return card_type

        return "unknown"

    def _extract_name(self, frontmatter: dict, file_path: Path) -> str | None:
        """Extract entity name from frontmatter or filename."""
        # Priority order
        for field in ("name", "title", "topic"):
            val = frontmatter.get(field)
            if val:
                return str(val).strip()

        # ID fields
        for field in ("memory_id", "secret_id", "knowledge_id", "thread_id"):
            val = frontmatter.get(field)
            if val:
                return str(val).strip()

        # File stem
        stem = file_path.stem
        if stem:
            return stem

        return None

    @staticmethod
    def _compute_content_hash(content: str) -> str:
        """SHA-256 hash of file content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Internal: Connection extraction
    # ------------------------------------------------------------------

    def _extract_connections(
        self,
        entity_id: str,
        frontmatter: dict,
        card_type: str,
        entity_keys: dict[str, str],
        alias_map: dict[str, str],
        rp_folder: str,
    ) -> list[dict[str, str | None]]:
        """Extract typed connections from frontmatter fields."""
        connections: list[dict[str, str | None]] = []

        for rule_type, rule_field, conn_type in CONNECTION_RULES:
            if card_type != rule_type:
                continue

            value = frontmatter.get(rule_field)
            if value is None:
                continue

            # Special handling per field type
            if rule_field == "relationships":
                connections.extend(
                    self._parse_relationships(entity_id, value, entity_keys, alias_map, rp_folder)
                )
            elif rule_field == "npc_trust_levels":
                connections.extend(
                    self._parse_trust_levels(entity_id, value, entity_keys, alias_map, rp_folder)
                )
            elif rule_field == "who_else_remembers":
                connections.extend(
                    self._parse_who_remembers(entity_id, value, entity_keys, alias_map, rp_folder)
                )
            elif rule_field == "connected_locations":
                connections.extend(
                    self._parse_connected_locations(entity_id, value, entity_keys, alias_map, rp_folder)
                )
            elif rule_field == "regular_occupants":
                connections.extend(
                    self._parse_occupants(entity_id, value, conn_type, entity_keys, alias_map, rp_folder)
                )
            elif isinstance(value, list):
                for item in value:
                    ref = str(item) if not isinstance(item, dict) else None
                    if ref:
                        target = self._resolve_ref(ref, entity_keys, alias_map, rp_folder)
                        connections.append({
                            "from": entity_id,
                            "to": target,
                            "type": conn_type,
                            "field": rule_field,
                            "role": None,
                        })
            elif isinstance(value, dict):
                for key in value:
                    target = self._resolve_ref(str(key), entity_keys, alias_map, rp_folder)
                    connections.append({
                        "from": entity_id,
                        "to": target,
                        "type": conn_type,
                        "field": rule_field,
                        "role": None,
                    })
            elif isinstance(value, str):
                target = self._resolve_ref(value, entity_keys, alias_map, rp_folder)
                connections.append({
                    "from": entity_id,
                    "to": target,
                    "type": conn_type,
                    "field": rule_field,
                    "role": None,
                })

        return connections

    def _parse_relationships(
        self, entity_id: str, value: Any,
        entity_keys: dict, alias_map: dict, rp_folder: str,
    ) -> list[dict]:
        """Parse relationships — list of dicts OR dict of dicts."""
        conns = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    role = item.get("role") or item.get("type")
                    if name:
                        target = self._resolve_ref(str(name), entity_keys, alias_map, rp_folder)
                        conns.append({
                            "from": entity_id, "to": target,
                            "type": "has_relationship",
                            "field": "relationships",
                            "role": str(role) if role else None,
                        })
        elif isinstance(value, dict):
            for name, details in value.items():
                role = None
                if isinstance(details, dict):
                    role = details.get("type") or details.get("role")
                target = self._resolve_ref(str(name), entity_keys, alias_map, rp_folder)
                conns.append({
                    "from": entity_id, "to": target,
                    "type": "has_relationship",
                    "field": "relationships",
                    "role": str(role) if role else None,
                })
        return conns

    def _parse_trust_levels(
        self, entity_id: str, value: Any,
        entity_keys: dict, alias_map: dict, rp_folder: str,
    ) -> list[dict]:
        """Parse npc_trust_levels dict: {Name: score}."""
        conns = []
        if isinstance(value, dict):
            for name in value:
                target = self._resolve_ref(str(name), entity_keys, alias_map, rp_folder)
                conns.append({
                    "from": entity_id, "to": target,
                    "type": "trusts",
                    "field": "npc_trust_levels",
                    "role": None,
                })
        return conns

    def _parse_who_remembers(
        self, entity_id: str, value: Any,
        entity_keys: dict, alias_map: dict, rp_folder: str,
    ) -> list[dict]:
        """Parse who_else_remembers: {CharName: {perspective, memory_ref}}."""
        conns = []
        if isinstance(value, dict):
            for char_name, details in value.items():
                target = self._resolve_ref(str(char_name), entity_keys, alias_map, rp_folder)
                conns.append({
                    "from": entity_id, "to": target,
                    "type": "shared_memory",
                    "field": "who_else_remembers",
                    "role": None,
                })
                # If memory_ref is present and not null, create related_memory
                if isinstance(details, dict):
                    ref = details.get("memory_ref")
                    if ref:
                        mem_target = self._resolve_ref(str(ref), entity_keys, alias_map, rp_folder)
                        conns.append({
                            "from": entity_id, "to": mem_target,
                            "type": "related_memory",
                            "field": "who_else_remembers.memory_ref",
                            "role": None,
                        })
        return conns

    def _parse_connected_locations(
        self, entity_id: str, value: Any,
        entity_keys: dict, alias_map: dict, rp_folder: str,
    ) -> list[dict]:
        """Parse connected_locations — strings OR dicts with file key."""
        conns = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    name = item.get("file", item.get("name", ""))
                    role = item.get("relationship")
                else:
                    name = str(item)
                    role = None
                if name:
                    target = self._resolve_ref(str(name), entity_keys, alias_map, rp_folder)
                    conns.append({
                        "from": entity_id, "to": target,
                        "type": "connects_to",
                        "field": "connected_locations",
                        "role": str(role) if role else None,
                    })
        elif isinstance(value, str):
            target = self._resolve_ref(value, entity_keys, alias_map, rp_folder)
            conns.append({
                "from": entity_id, "to": target,
                "type": "connects_to",
                "field": "connected_locations",
                "role": None,
            })
        return conns

    def _parse_occupants(
        self, entity_id: str, value: Any, conn_type: str,
        entity_keys: dict, alias_map: dict, rp_folder: str,
    ) -> list[dict]:
        """Parse regular_occupants with parenthetical stripping."""
        conns = []
        if isinstance(value, list):
            for item in value:
                raw = str(item)
                name = strip_parenthetical(raw)
                role_match = None
                # Extract the parenthetical as the role
                import re
                paren = re.search(r"\(([^)]+)\)", raw)
                if paren:
                    role_match = paren.group(1)
                target = self._resolve_ref(name, entity_keys, alias_map, rp_folder)
                conns.append({
                    "from": entity_id, "to": target,
                    "type": conn_type,
                    "field": "regular_occupants",
                    "role": role_match,
                })
        return conns

    # ------------------------------------------------------------------
    # Internal: Alias / keyword extraction
    # ------------------------------------------------------------------

    def _extract_aliases(
        self, entity_id: str, frontmatter: dict, file_path: Path,
    ) -> list[str]:
        """Extract all alias strings for an entity (normalized)."""
        aliases: list[str] = []

        # aliases field
        fm_aliases = frontmatter.get("aliases")
        if isinstance(fm_aliases, list):
            for a in fm_aliases:
                key = normalize_key(str(a))
                if key:
                    aliases.append(key)

        # ID fields
        for field in ("memory_id", "secret_id", "knowledge_id", "thread_id"):
            val = frontmatter.get(field)
            if val:
                aliases.append(normalize_key(str(val)))
                # Also add underscore-to-space variant
                space_key = id_to_key(str(val))
                if space_key and space_key not in aliases:
                    aliases.append(space_key)

        # File stem
        stem_key = file_to_key(file_path.name)
        if stem_key and stem_key not in aliases:
            aliases.append(stem_key)

        return aliases

    def _extract_keywords(self, entity_id: str, frontmatter: dict) -> list[str]:
        """Extract search keywords for an entity."""
        keywords: set[str] = set()

        # triggers field
        triggers = frontmatter.get("triggers")
        if isinstance(triggers, list):
            for t in triggers:
                kw = normalize_key(str(t))
                if kw:
                    keywords.add(kw)

        # Full name
        name = frontmatter.get("name") or frontmatter.get("title") or frontmatter.get("topic")
        if name:
            full = normalize_key(str(name))
            if full:
                keywords.add(full)
            # Individual words (3+ chars)
            for word in str(name).split():
                w = normalize_key(word)
                if len(w) >= 3:
                    keywords.add(w)

        # Aliases
        fm_aliases = frontmatter.get("aliases")
        if isinstance(fm_aliases, list):
            for a in fm_aliases:
                kw = normalize_key(str(a))
                if kw:
                    keywords.add(kw)

        return list(keywords)

    # ------------------------------------------------------------------
    # Internal: Reference resolution
    # ------------------------------------------------------------------

    def _resolve_ref(
        self,
        ref: str,
        entity_keys: dict[str, str],
        alias_map: dict[str, str],
        rp_folder: str,
    ) -> str:
        """Resolve a reference string to an entity ID.

        Tries 4 strategies. Falls back to ``rp_folder:normalize_key(ref)``.
        """
        if not ref:
            return f"{rp_folder}:"

        raw = str(ref)

        # Strategy 1: Direct normalized key
        key = normalize_key(raw)
        if key in entity_keys:
            return entity_keys[key]
        if key in alias_map:
            return alias_map[key]

        # Strategy 2: Strip .md extension
        key2 = file_to_key(raw)
        if key2 != key:
            if key2 in entity_keys:
                return entity_keys[key2]
            if key2 in alias_map:
                return alias_map[key2]

        # Strategy 3: Underscore to space
        key3 = id_to_key(raw)
        if key3 != key:
            if key3 in entity_keys:
                return entity_keys[key3]
            if key3 in alias_map:
                return alias_map[key3]

        # Strategy 4: Strip parenthetical
        key4 = normalize_key(strip_parenthetical(raw))
        if key4 != key:
            if key4 in entity_keys:
                return entity_keys[key4]
            if key4 in alias_map:
                return alias_map[key4]

        # Unresolved — use normalized key with rp_folder prefix
        return f"{rp_folder}:{key}"

    # ------------------------------------------------------------------
    # Internal: DB helpers
    # ------------------------------------------------------------------

    async def _clear_rp(self, rp_folder: str) -> None:
        """Remove all indexed data for an RP folder."""
        # Get entity IDs for this RP
        rows = await self.db.fetch_all(
            "SELECT id FROM story_cards WHERE rp_folder = ?", [rp_folder]
        )
        entity_ids = [r["id"] for r in rows]

        if entity_ids:
            placeholders = ",".join("?" * len(entity_ids))
            for table, col in [
                ("entity_connections", "from_entity"),
                ("entity_connections", "to_entity"),
                ("entity_aliases", "entity_id"),
                ("entity_keywords", "entity_id"),
            ]:
                future = await self.db.enqueue_write(
                    f"DELETE FROM {table} WHERE {col} IN ({placeholders})",
                    entity_ids,
                    priority=PRIORITY_REINDEX,
                )
                await future

        future = await self.db.enqueue_write(
            "DELETE FROM story_cards WHERE rp_folder = ?",
            [rp_folder],
            priority=PRIORITY_REINDEX,
        )
        await future

    async def _remove_entity(self, entity_id: str) -> None:
        """Remove a single entity and its connections/aliases/keywords."""
        for sql in [
            "DELETE FROM entity_connections WHERE from_entity = ? OR to_entity = ?",
            "DELETE FROM entity_aliases WHERE entity_id = ?",
            "DELETE FROM entity_keywords WHERE entity_id = ?",
            "DELETE FROM story_cards WHERE id = ?",
        ]:
            params = [entity_id, entity_id] if "from_entity" in sql else [entity_id]
            future = await self.db.enqueue_write(sql, params, priority=PRIORITY_REINDEX)
            await future

    async def _load_resolution_maps(
        self, rp_folder: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Load entity keys and alias map from DB for incremental indexing."""
        rows = await self.db.fetch_all(
            "SELECT id FROM story_cards WHERE rp_folder = ?", [rp_folder]
        )
        entity_keys: dict[str, str] = {}
        for r in rows:
            eid = r["id"]
            key = eid.split(":", 1)[1] if ":" in eid else eid
            entity_keys[key] = eid

        alias_rows = await self.db.fetch_all(
            """SELECT ea.alias, ea.entity_id FROM entity_aliases ea
               JOIN story_cards sc ON ea.entity_id = sc.id
               WHERE sc.rp_folder = ?""",
            [rp_folder],
        )
        alias_map: dict[str, str] = {r["alias"]: r["entity_id"] for r in alias_rows}

        return entity_keys, alias_map
