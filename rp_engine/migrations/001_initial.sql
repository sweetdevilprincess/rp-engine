-- =============================================
-- Core Tables
-- =============================================

-- RP sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    metadata TEXT  -- JSON
);

-- Chat exchanges
CREATE TABLE IF NOT EXISTS exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    in_story_timestamp TEXT,
    location TEXT,
    npcs_involved TEXT,  -- JSON array
    analysis_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    metadata TEXT  -- JSON
);

-- Character state
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    name TEXT NOT NULL,
    card_path TEXT,
    is_player_character BOOLEAN DEFAULT FALSE,
    importance TEXT,
    primary_archetype TEXT,
    secondary_archetype TEXT,
    behavioral_modifiers TEXT,  -- JSON array
    location TEXT,
    conditions TEXT,  -- JSON array
    emotional_state TEXT,
    last_seen TEXT,
    updated_at TEXT,
    UNIQUE(rp_folder, branch, name)
);

-- Relationships and trust
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    character_a TEXT NOT NULL,
    character_b TEXT NOT NULL,
    initial_trust_score INTEGER DEFAULT 0,
    trust_modification_sum INTEGER DEFAULT 0,
    trust_stage TEXT,
    dynamic TEXT,
    session_trust_gained INTEGER DEFAULT 0,
    session_trust_lost INTEGER DEFAULT 0,
    updated_at TEXT,
    UNIQUE(rp_folder, branch, character_a, character_b)
);

-- Trust modifications
CREATE TABLE IF NOT EXISTS trust_modifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relationship_id INTEGER REFERENCES relationships(id),
    date TEXT,
    change INTEGER,
    direction TEXT,
    reason TEXT,
    exchange_id INTEGER REFERENCES exchanges(id),
    created_at TEXT
);

-- Plot thread definitions
CREATE TABLE IF NOT EXISTS plot_threads (
    id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    name TEXT NOT NULL,
    card_path TEXT,
    thread_type TEXT,
    priority TEXT,
    status TEXT DEFAULT 'active',
    phase TEXT,
    keywords TEXT,  -- JSON array
    thresholds TEXT,  -- JSON object
    consequences TEXT,  -- JSON object
    related_characters TEXT,  -- JSON array
    updated_at TEXT,
    PRIMARY KEY(id, rp_folder)
);

-- Plot thread counters (per-branch)
CREATE TABLE IF NOT EXISTS thread_counters (
    thread_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    current_counter INTEGER DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY(thread_id, rp_folder, branch),
    FOREIGN KEY(thread_id, rp_folder) REFERENCES plot_threads(id, rp_folder)
);

-- Significant events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    in_story_timestamp TEXT,
    event TEXT NOT NULL,
    characters TEXT,  -- JSON array
    significance TEXT,
    exchange_id INTEGER REFERENCES exchanges(id),
    created_at TEXT
);

-- Scene context
CREATE TABLE IF NOT EXISTS scene_context (
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    location TEXT,
    time_of_day TEXT,
    mood TEXT,
    in_story_timestamp TEXT,
    updated_at TEXT,
    PRIMARY KEY(rp_folder, branch)
);

-- =============================================
-- Story Card Index Tables
-- =============================================

-- Story card metadata cache
CREATE TABLE IF NOT EXISTS story_cards (
    id TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    file_path TEXT NOT NULL,
    card_type TEXT NOT NULL,
    name TEXT NOT NULL,
    importance TEXT,
    summary TEXT,
    frontmatter TEXT,  -- JSON
    content TEXT,
    content_hash TEXT,
    file_mtime REAL,
    indexed_at TEXT
);

-- Entity connections
CREATE TABLE IF NOT EXISTS entity_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL,
    to_entity TEXT NOT NULL,
    connection_type TEXT NOT NULL,
    field TEXT,
    role TEXT
);

-- Entity aliases
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY(alias, entity_id)
);

-- Entity keywords
CREATE TABLE IF NOT EXISTS entity_keywords (
    keyword TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY(keyword, entity_id)
);

-- =============================================
-- Vector Search Tables
-- =============================================

-- Vector embeddings
CREATE TABLE IF NOT EXISTS vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    file_path TEXT,
    chunk_index INTEGER,
    total_chunks INTEGER,
    rp_folder TEXT,
    card_type TEXT,
    metadata TEXT,  -- JSON
    created_at TEXT
);

-- FTS5 for BM25 keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS vectors_fts USING fts5(
    content,
    content='vectors',
    content_rowid='id'
);

-- File indexing state
CREATE TABLE IF NOT EXISTS indexed_files (
    file_path TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    mtime REAL,
    size INTEGER,
    chunk_count INTEGER,
    indexed_at TEXT
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS vectors_ai AFTER INSERT ON vectors BEGIN
    INSERT INTO vectors_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS vectors_ad AFTER DELETE ON vectors BEGIN
    INSERT INTO vectors_fts(vectors_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS vectors_au AFTER UPDATE ON vectors BEGIN
    INSERT INTO vectors_fts(vectors_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO vectors_fts(rowid, content) VALUES (new.id, new.content);
END;

-- =============================================
-- Branch Management
-- =============================================

CREATE TABLE IF NOT EXISTS branches (
    name TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    created_from TEXT,
    created_at TEXT,
    branch_point_session TEXT,
    branch_point_exchange INTEGER,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    PRIMARY KEY(name, rp_folder)
);

-- =============================================
-- Utility Tables
-- =============================================

-- Card gap tracking
CREATE TABLE IF NOT EXISTS card_gaps (
    entity_name TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    suggested_type TEXT,
    seen_count INTEGER DEFAULT 1,
    first_seen TEXT,
    last_seen TEXT,
    PRIMARY KEY(entity_name, rp_folder)
);

-- Configuration
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT  -- JSON
);

-- Context sent tracking
CREATE TABLE IF NOT EXISTS context_sent (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    entity_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    sent_at_turn INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY(session_id, entity_id)
);

-- Situational triggers
CREATE TABLE IF NOT EXISTS situational_triggers (
    id TEXT PRIMARY KEY,
    rp_folder TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    inject_type TEXT NOT NULL,
    inject_content TEXT,
    inject_card_path TEXT,
    conditions TEXT NOT NULL,
    match_mode TEXT DEFAULT 'any',
    priority INTEGER DEFAULT 0,
    cooldown_turns INTEGER DEFAULT 0,
    last_fired_turn INTEGER,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TEXT,
    updated_at TEXT
);

-- =============================================
-- Indexes
-- =============================================

CREATE INDEX IF NOT EXISTS idx_exchanges_session ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_rp_branch ON exchanges(rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_characters_rp_branch ON characters(rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_relationships_rp_branch ON relationships(rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_trust_mods_relationship ON trust_modifications(relationship_id);
CREATE INDEX IF NOT EXISTS idx_trust_mods_exchange ON trust_modifications(exchange_id);
CREATE INDEX IF NOT EXISTS idx_events_rp_branch ON events(rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_events_exchange ON events(exchange_id);
CREATE INDEX IF NOT EXISTS idx_story_cards_rp ON story_cards(rp_folder);
CREATE INDEX IF NOT EXISTS idx_story_cards_type ON story_cards(card_type);
CREATE INDEX IF NOT EXISTS idx_entity_connections_from ON entity_connections(from_entity);
CREATE INDEX IF NOT EXISTS idx_entity_connections_to ON entity_connections(to_entity);
CREATE INDEX IF NOT EXISTS idx_vectors_rp ON vectors(rp_folder);
CREATE INDEX IF NOT EXISTS idx_vectors_file ON vectors(file_path);
CREATE INDEX IF NOT EXISTS idx_branches_rp ON branches(rp_folder);
CREATE INDEX IF NOT EXISTS idx_triggers_rp ON situational_triggers(rp_folder);
CREATE INDEX IF NOT EXISTS idx_context_sent_session ON context_sent(session_id);
