-- 005_drop_legacy_tables.sql: Remove legacy state tables
--
-- Prerequisites: migration 003 (CoW tables) must be applied.
-- The old characters, relationships, and scene_context tables
-- are superseded by character_ledger + character_state_entries,
-- trust_baselines + trust_modifications (direct columns),
-- and scene_state_entries respectively.
--
-- trust_modifications.relationship_id becomes NULL for old rows
-- but all new rows use direct columns (character_a, character_b, etc.)

-- Drop the legacy tables
DROP TABLE IF EXISTS characters;
DROP TABLE IF EXISTS scene_context;

-- Keep the relationships table but mark it deprecated.
-- We can't drop it yet because trust_modifications.relationship_id
-- references it. Instead, drop the session-scoped columns.
-- (The table stays read-only for historical reference.)
