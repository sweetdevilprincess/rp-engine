-- Custom state schema definitions
CREATE TABLE IF NOT EXISTS custom_state_schemas (
    id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    config TEXT,
    belongs_to TEXT,
    inject_as TEXT DEFAULT 'hidden',
    display_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(rp_folder, id)
);

-- Custom state entries (CoW values, per exchange)
CREATE TABLE IF NOT EXISTS custom_state_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    entity_id TEXT,
    value TEXT NOT NULL,
    changed_by TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(schema_id, rp_folder) REFERENCES custom_state_schemas(id, rp_folder)
);
CREATE INDEX IF NOT EXISTS idx_cse_lookup
    ON custom_state_entries(schema_id, rp_folder, branch, entity_id, exchange_number);
