-- Per-RP chunking strategy overrides
CREATE TABLE IF NOT EXISTS rp_chunking_config (
    rp_folder TEXT NOT NULL PRIMARY KEY,
    strategy TEXT NOT NULL DEFAULT 'fixed',
    chunk_size INTEGER NOT NULL DEFAULT 1000,
    chunk_overlap INTEGER NOT NULL DEFAULT 200,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
