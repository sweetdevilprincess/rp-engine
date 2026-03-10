"""Custom state management — generic tracked fields with CoW entries."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

from rp_engine.database import PRIORITY_ANALYSIS, PRIORITY_EXCHANGE, Database
from rp_engine.models.custom_state import (
    CustomStateSchema,
    CustomStateSnapshot,
    CustomStateValue,
    PresetInfo,
)
from rp_engine.services.state_entry_resolver import StateEntryResolver
from rp_engine.utils.json_helpers import safe_parse_json
from rp_engine.utils.lru_cache import LRUCache

logger = logging.getLogger(__name__)

PRESETS_DIR = Path(__file__).parent.parent / "presets"

# Module-level preset cache: {file_path: (mtime, parsed_data)}
_preset_cache: LRUCache[str, tuple[float, dict]] = LRUCache(maxsize=32)


def _load_preset(path: Path) -> dict | None:
    """Load a preset YAML file with mtime caching."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    cached = _preset_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        _preset_cache.put(key, (mtime, data))
        return data
    except Exception:
        return None


class CustomStateManager:
    """Manages custom state schemas, values, and presets."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._resolver = StateEntryResolver(
            db, "custom_state_entries", ["schema_id", "entity_id"]
        )
        self._branch_manager = None  # Late-bound via configure()

    def configure(self, *, branch_manager) -> None:
        """Late-bind dependencies that aren't available at construction time."""
        self._branch_manager = branch_manager

    # ===================================================================
    # Schema CRUD
    # ===================================================================

    async def list_schemas(self, rp_folder: str) -> list[CustomStateSchema]:
        """List all custom state schemas for an RP."""
        rows = await self.db.fetch_all(
            "SELECT * FROM custom_state_schemas WHERE rp_folder = ? ORDER BY display_order, name",
            [rp_folder],
        )
        return [self._row_to_schema(r) for r in rows]

    async def create_schema(self, schema: CustomStateSchema, rp_folder: str) -> CustomStateSchema:
        """Create a new custom state schema."""
        now = datetime.now(UTC).isoformat()
        config_json = json.dumps(schema.config) if schema.config else None

        future = await self.db.enqueue_write(
            """INSERT INTO custom_state_schemas
                   (id, rp_folder, category, name, data_type, config,
                    belongs_to, inject_as, display_order, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [schema.id, rp_folder, schema.category, schema.name,
             schema.data_type, config_json, schema.belongs_to,
             schema.inject_as, schema.display_order, now],
            priority=PRIORITY_EXCHANGE,
        )
        await future
        schema.rp_folder = rp_folder
        return schema

    async def delete_schema(self, schema_id: str, rp_folder: str) -> bool:
        """Delete a custom state schema and its entries."""
        future = await self.db.enqueue_write(
            "DELETE FROM custom_state_entries WHERE schema_id = ? AND rp_folder = ?",
            [schema_id, rp_folder],
            priority=PRIORITY_EXCHANGE,
        )
        await future
        future = await self.db.enqueue_write(
            "DELETE FROM custom_state_schemas WHERE id = ? AND rp_folder = ?",
            [schema_id, rp_folder],
            priority=PRIORITY_EXCHANGE,
        )
        await future
        return True

    # ===================================================================
    # Values
    # ===================================================================

    async def get_all_values(
        self, rp_folder: str, branch: str = "main"
    ) -> list[CustomStateValue]:
        """Get all latest custom state values for an RP/branch."""
        rows = await self._resolver.resolve_all_latest(rp_folder, branch)
        return [
            CustomStateValue(
                schema_id=r["schema_id"],
                entity_id=r.get("entity_id"),
                value=self._parse_value(r.get("value")),
                exchange_number=r.get("exchange_number"),
                changed_by=r.get("changed_by"),
                reason=r.get("reason"),
            )
            for r in rows
        ]

    async def get_value(
        self,
        schema_id: str,
        rp_folder: str,
        branch: str = "main",
        entity_id: str | None = None,
    ) -> CustomStateValue | None:
        """Get the latest value for a specific schema/entity."""
        row = await self._resolver.resolve_latest(
            rp_folder, branch,
            schema_id=schema_id, entity_id=entity_id or "",
        )
        if not row:
            return None
        return CustomStateValue(
            schema_id=row["schema_id"],
            entity_id=row.get("entity_id"),
            value=self._parse_value(row.get("value")),
            exchange_number=row.get("exchange_number"),
            changed_by=row.get("changed_by"),
            reason=row.get("reason"),
        )

    async def set_value(
        self,
        schema_id: str,
        value: str | dict | list | int | float,
        rp_folder: str,
        branch: str = "main",
        entity_id: str | None = None,
        exchange_number: int | None = None,
        changed_by: str = "manual",
        reason: str | None = None,
    ) -> CustomStateValue:
        """Set a custom state value (CoW entry)."""
        now = datetime.now(UTC).isoformat()

        if exchange_number is None:
            if self._branch_manager:
                exchange_number = await self._branch_manager.get_latest_exchange_number(rp_folder, branch)
            else:
                val = await self.db.fetch_val(
                    "SELECT MAX(exchange_number) FROM exchanges WHERE rp_folder = ? AND branch = ?",
                    [rp_folder, branch],
                )
                exchange_number = val or 0

        value_json = json.dumps(value) if not isinstance(value, str) else value

        future = await self.db.enqueue_write(
            """INSERT INTO custom_state_entries
                   (schema_id, rp_folder, branch, exchange_number,
                    entity_id, value, changed_by, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [schema_id, rp_folder, branch, exchange_number,
             entity_id or "", value_json, changed_by, reason, now],
            priority=PRIORITY_ANALYSIS,
        )
        await future

        return CustomStateValue(
            schema_id=schema_id,
            entity_id=entity_id,
            value=value,
            exchange_number=exchange_number,
            changed_by=changed_by,
            reason=reason,
        )

    async def get_snapshot(
        self, rp_folder: str, branch: str = "main"
    ) -> CustomStateSnapshot:
        """Get full custom state snapshot (schemas + values)."""
        schemas = await self.list_schemas(rp_folder)
        values = await self.get_all_values(rp_folder, branch)
        return CustomStateSnapshot(schemas=schemas, values=values)

    # ===================================================================
    # Presets
    # ===================================================================

    def list_presets(self) -> list[PresetInfo]:
        """List available preset templates."""
        presets = []
        if PRESETS_DIR.exists():
            for f in PRESETS_DIR.glob("*.yaml"):
                data = _load_preset(f)
                if data:
                    presets.append(PresetInfo(
                        name=f.stem,
                        description=data.get("description"),
                        schema_count=len(data.get("schemas", [])),
                    ))
        return presets

    async def apply_preset(self, preset_name: str, rp_folder: str) -> list[CustomStateSchema]:
        """Apply a preset template to an RP folder."""
        preset_path = PRESETS_DIR / f"{preset_name}.yaml"
        data = _load_preset(preset_path)
        if data is None:
            raise ValueError(f"Preset '{preset_name}' not found")
        schemas_data = data.get("schemas", [])
        created = []

        for s in schemas_data:
            schema = CustomStateSchema(
                id=s["id"],
                rp_folder=rp_folder,
                category=s.get("category", "general"),
                name=s["name"],
                data_type=s["data_type"],
                config=s.get("config"),
                belongs_to=s.get("belongs_to"),
                inject_as=s.get("inject_as", "hidden"),
                display_order=s.get("display_order", 0),
            )
            try:
                result = await self.create_schema(schema, rp_folder)
                created.append(result)
            except Exception as e:
                logger.warning("Failed to create schema %s: %s", s["id"], e)

        return created

    # ===================================================================
    # Helpers
    # ===================================================================

    @staticmethod
    def _row_to_schema(row: dict) -> CustomStateSchema:
        config = safe_parse_json(row.get("config"), default=None)

        return CustomStateSchema(
            id=row["id"],
            rp_folder=row.get("rp_folder"),
            category=row["category"],
            name=row["name"],
            data_type=row["data_type"],
            config=config,
            belongs_to=row.get("belongs_to"),
            inject_as=row.get("inject_as", "hidden"),
            display_order=row.get("display_order", 0),
        )

    @staticmethod
    def _parse_value(raw: str | None):
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
