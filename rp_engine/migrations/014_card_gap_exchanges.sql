-- Track which exchanges contributed to each card gap entity.
-- Used by scene-aware card generation to provide rich narrative context.
CREATE TABLE IF NOT EXISTS card_gap_exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    chunk_text TEXT,
    mention_type TEXT NOT NULL DEFAULT 'peripheral',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_name, rp_folder, exchange_number, branch)
);

CREATE INDEX IF NOT EXISTS idx_gap_exchanges_lookup
    ON card_gap_exchanges(entity_name, rp_folder, branch);
