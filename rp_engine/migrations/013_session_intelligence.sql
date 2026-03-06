-- Session summaries and recaps for Phase 6: Session Intelligence & Chat

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    narrative_summary TEXT NOT NULL,
    key_moments TEXT,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_recaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    session_id TEXT,
    style TEXT NOT NULL DEFAULT 'standard',
    recap_text TEXT NOT NULL,
    state_hash TEXT,
    generated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_session_recaps_folder_branch
    ON session_recaps(rp_folder, branch);
