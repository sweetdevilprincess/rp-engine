-- Analysis manifest tracking: groups all state changes from one analysis run
-- so they can be undone, previewed, or replayed.

CREATE TABLE IF NOT EXISTS analysis_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_id INTEGER NOT NULL,
    exchange_number INTEGER NOT NULL,
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    model_used TEXT,
    raw_response TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    undone_at TEXT,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
);
CREATE INDEX IF NOT EXISTS idx_manifests_exchange
    ON analysis_manifests(rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_manifests_status
    ON analysis_manifests(rp_folder, branch, status);

CREATE TABLE IF NOT EXISTS analysis_manifest_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manifest_id INTEGER NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    operation TEXT NOT NULL DEFAULT 'insert',
    FOREIGN KEY (manifest_id) REFERENCES analysis_manifests(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_manifest_entries
    ON analysis_manifest_entries(manifest_id);
