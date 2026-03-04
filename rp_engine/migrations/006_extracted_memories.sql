-- Extracted memories from LLM analysis pipeline
CREATE TABLE IF NOT EXISTS extracted_memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder   TEXT    NOT NULL,
    branch      TEXT    NOT NULL DEFAULT 'main',
    exchange_id INTEGER NOT NULL REFERENCES exchanges(id) ON DELETE CASCADE,
    session_id  TEXT,
    description TEXT    NOT NULL,
    significance TEXT,
    characters  TEXT,   -- JSON array of character names
    in_story_timestamp TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_extracted_memories_session
    ON extracted_memories(rp_folder, branch, session_id);
CREATE INDEX IF NOT EXISTS idx_extracted_memories_exchange
    ON extracted_memories(exchange_id);
