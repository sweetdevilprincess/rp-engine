-- 002_branching.sql: State history tables for rewind + checkpoints

-- Character state history: logs each field change with exchange_id for rewind
CREATE TABLE IF NOT EXISTS character_state_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_id INTEGER NOT NULL REFERENCES exchanges(id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_char_history_exchange ON character_state_history(exchange_id);
CREATE INDEX IF NOT EXISTS idx_char_history_char ON character_state_history(character_id, branch);

-- Scene context history: same pattern for scene state
CREATE TABLE IF NOT EXISTS scene_context_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_id INTEGER NOT NULL REFERENCES exchanges(id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scene_history_exchange ON scene_context_history(exchange_id);

-- Checkpoints: named save points within a branch (restore = rewind to exchange_number)
CREATE TABLE IF NOT EXISTS checkpoints (
    name TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(name, rp_folder, branch)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_branch ON checkpoints(rp_folder, branch);
