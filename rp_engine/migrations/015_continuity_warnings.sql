-- Continuity warnings: track detected narrative contradictions.
-- Populated by ContinuityChecker during post-exchange analysis.
CREATE TABLE IF NOT EXISTS continuity_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    entity_name TEXT NOT NULL,
    category TEXT NOT NULL,
    current_claim TEXT NOT NULL,
    current_exchange INTEGER NOT NULL,
    past_claim TEXT NOT NULL,
    past_exchange INTEGER NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    explanation TEXT,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_continuity_lookup
    ON continuity_warnings(rp_folder, branch, resolved);
