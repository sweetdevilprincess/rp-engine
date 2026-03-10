-- Migration 024: Schema cleanup
-- Drops phantom tables that may still exist in older databases,
-- plus the legacy relationships table (superseded by trust_baselines + trust_modifications).
--
-- trust_modifications.relationship_id has an FK to relationships(id),
-- so we must recreate the table without that FK before dropping relationships.

DROP TABLE IF EXISTS character_state_history;
DROP TABLE IF EXISTS scene_context_history;

-- Recreate trust_modifications without the FK to relationships
CREATE TABLE IF NOT EXISTS trust_modifications_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relationship_id INTEGER,  -- legacy column, no FK constraint
    date TEXT,
    change INTEGER,
    direction TEXT,
    reason TEXT,
    exchange_id INTEGER REFERENCES exchanges(id),
    created_at TEXT,
    character_a TEXT,
    character_b TEXT,
    branch TEXT,
    exchange_number INTEGER,
    rp_folder TEXT
);

INSERT INTO trust_modifications_new
    SELECT id, relationship_id, date, change, direction, reason,
           exchange_id, created_at, character_a, character_b,
           branch, exchange_number, rp_folder
    FROM trust_modifications;

DROP TABLE trust_modifications;
ALTER TABLE trust_modifications_new RENAME TO trust_modifications;

-- Recreate indexes on the new table
CREATE INDEX IF NOT EXISTS idx_trust_mods_exchange ON trust_modifications(exchange_id);
CREATE INDEX IF NOT EXISTS idx_trust_mods_direct
    ON trust_modifications(character_a, character_b, rp_folder, branch, exchange_number);

-- Now safe to drop relationships
DROP TABLE IF EXISTS relationships;
