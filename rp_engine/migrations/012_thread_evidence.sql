-- Thread evidence linking: records which exchange triggered each counter change
CREATE TABLE IF NOT EXISTS thread_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    chunk_text TEXT,
    keyword_matched TEXT,
    counter_before INTEGER NOT NULL,
    counter_after INTEGER NOT NULL,
    direction TEXT NOT NULL DEFAULT 'increment',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_thread_evidence_lookup
    ON thread_evidence(thread_id, rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_thread_evidence_exchange
    ON thread_evidence(rp_folder, branch, exchange_number);
