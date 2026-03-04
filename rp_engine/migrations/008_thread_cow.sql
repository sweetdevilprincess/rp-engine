-- Thread counter entries: one row per exchange, enables rewind
-- Replaces the upsert pattern on thread_counters with append-only CoW entries
CREATE TABLE IF NOT EXISTS thread_counter_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    counter_value INTEGER NOT NULL DEFAULT 0,
    mentioned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(thread_id, rp_folder) REFERENCES plot_threads(id, rp_folder)
);
CREATE INDEX IF NOT EXISTS idx_tce_lookup
    ON thread_counter_entries(thread_id, rp_folder, branch, exchange_number);

-- Thread status entries: branch-divergent thread status/phase
CREATE TABLE IF NOT EXISTS thread_status_entries (
    thread_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    status TEXT,
    phase TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(thread_id, rp_folder, branch, exchange_number),
    FOREIGN KEY(thread_id, rp_folder) REFERENCES plot_threads(id, rp_folder)
);
