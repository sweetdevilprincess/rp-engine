-- Exchange variants for swipe/regenerate
-- Each variant stores an alternative assistant response for the same exchange

CREATE TABLE IF NOT EXISTS exchange_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_id INTEGER NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    assistant_response TEXT NOT NULL,
    model_used TEXT,
    temperature REAL,
    is_active BOOLEAN NOT NULL DEFAULT 0,
    continue_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_variants_exchange ON exchange_variants(exchange_id);
CREATE INDEX IF NOT EXISTS idx_variants_rp ON exchange_variants(rp_folder, branch, exchange_number);
