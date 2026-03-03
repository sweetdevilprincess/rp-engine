-- 003_ledger_cow.sql: Character Ledger + Copy-on-Write Branching System
--
-- Adds new tables alongside existing ones (no breakage).
-- Existing tables (characters, relationships, scene_context, etc.) remain
-- until data migration (004) and cleanup (005) are run.

-- =============================================
-- Character Ledger: per-character version registry
-- =============================================
-- One entry per character per branch. Dormant until first appearance.
-- Resolution walks ancestry using this + branch metadata.
CREATE TABLE IF NOT EXISTS character_ledger (
    card_id TEXT NOT NULL,              -- references story_cards.id
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'dormant',  -- dormant | active
    activated_at_exchange INTEGER,      -- exchange_number when first appeared on this branch
    created_at TEXT NOT NULL,
    PRIMARY KEY (card_id, rp_folder, branch)
);

CREATE INDEX IF NOT EXISTS idx_char_ledger_branch ON character_ledger(rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_char_ledger_card ON character_ledger(card_id, rp_folder);

-- =============================================
-- Character Runtime State (copy-on-write)
-- =============================================
-- Full snapshot entries. Only written when something CHANGES on this branch.
-- NOT card data — just runtime: location, conditions, emotional_state, last_seen.
-- Resolution: find latest entry on current branch <= exchange_number, walk ancestry if none.
CREATE TABLE IF NOT EXISTS character_state_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    location TEXT,
    conditions TEXT,                     -- JSON array
    emotional_state TEXT,
    last_seen TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(card_id, rp_folder, branch, exchange_number)
);

CREATE INDEX IF NOT EXISTS idx_char_state_lookup
    ON character_state_entries(card_id, rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_char_state_branch
    ON character_state_entries(rp_folder, branch);

-- =============================================
-- Trust Baselines
-- =============================================
-- Snapshot of accumulated trust at branch creation point.
-- Card's initial_relationships seeds exchange 0 on main (never modified).
-- Each subsequent branch records the accumulated total as its starting point.
-- Parent chain data is NEVER deleted — baselines are reference points only.
CREATE TABLE IF NOT EXISTS trust_baselines (
    character_a TEXT NOT NULL,           -- card_id (trust holder)
    character_b TEXT NOT NULL,           -- card_id (trust target)
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    baseline_score INTEGER NOT NULL DEFAULT 0,
    baseline_stage TEXT,
    source_branch TEXT,                  -- parent branch this was computed from
    source_exchange INTEGER,             -- exchange_number on parent at snapshot time
    created_at TEXT NOT NULL,
    PRIMARY KEY (character_a, character_b, rp_folder, branch)
);

CREATE INDEX IF NOT EXISTS idx_trust_baselines_branch
    ON trust_baselines(rp_folder, branch);
CREATE INDEX IF NOT EXISTS idx_trust_baselines_lookup
    ON trust_baselines(character_a, character_b, rp_folder, branch);

-- =============================================
-- Scene State (copy-on-write)
-- =============================================
-- Replaces scene_context + scene_context_history.
-- Same CoW pattern as character_state_entries.
CREATE TABLE IF NOT EXISTS scene_state_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    location TEXT,
    time_of_day TEXT,
    mood TEXT,
    in_story_timestamp TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(rp_folder, branch, exchange_number)
);

CREATE INDEX IF NOT EXISTS idx_scene_state_lookup
    ON scene_state_entries(rp_folder, branch, exchange_number);

-- =============================================
-- Branch-Scoped Runtime Data
-- =============================================
-- These track runtime memories/knowledge/secrets alongside existing card files.
-- Scoped by branch ancestry (open/closed model).

CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,             -- stable unique ID for this memory
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    belongs_to TEXT NOT NULL,            -- character card_id who holds this memory
    title TEXT NOT NULL,
    summary TEXT,
    emotional_tone TEXT,                 -- positive | negative | complex | neutral | traumatic
    importance TEXT DEFAULT 'medium',    -- critical | high | medium | low
    characters_involved TEXT,            -- JSON array of card_ids
    what_learned TEXT,                   -- JSON array
    content TEXT,                        -- full narrative
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_branch
    ON memory_entries(rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_memory_character
    ON memory_entries(belongs_to, rp_folder, branch);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id TEXT NOT NULL,          -- stable unique ID
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    belongs_to TEXT NOT NULL,            -- character card_id
    topic TEXT NOT NULL,
    believes TEXT,                       -- JSON
    reality TEXT,                        -- JSON (if different from believes)
    confidence TEXT,                     -- certain | strong | moderate | uncertain | suspicion
    source TEXT,                         -- how they learned this
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_branch
    ON knowledge_entries(rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_knowledge_character
    ON knowledge_entries(belongs_to, rp_folder, branch);

CREATE TABLE IF NOT EXISTS secret_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    secret_card_id TEXT NOT NULL,        -- references the secret story card
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL,
    exchange_number INTEGER NOT NULL,
    change_type TEXT NOT NULL,           -- discovered_by | partially_revealed | suspected_by | fully_revealed
    character_card_id TEXT NOT NULL,     -- who discovered/suspects
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_secret_events_branch
    ON secret_events(rp_folder, branch, exchange_number);
CREATE INDEX IF NOT EXISTS idx_secret_events_secret
    ON secret_events(secret_card_id, rp_folder, branch);

-- =============================================
-- Modify trust_modifications (backwards compatible)
-- =============================================
-- Add direct columns so trust_modifications no longer needs JOIN through relationships table.
-- Nullable for backwards compat with existing rows.
ALTER TABLE trust_modifications ADD COLUMN character_a TEXT;
ALTER TABLE trust_modifications ADD COLUMN character_b TEXT;
ALTER TABLE trust_modifications ADD COLUMN branch TEXT;
ALTER TABLE trust_modifications ADD COLUMN exchange_number INTEGER;
ALTER TABLE trust_modifications ADD COLUMN rp_folder TEXT;

CREATE INDEX IF NOT EXISTS idx_trust_mods_new_lookup
    ON trust_modifications(character_a, character_b, rp_folder, branch, exchange_number);
