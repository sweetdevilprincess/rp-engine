-- Exchange bookmarks and annotations
-- Phase 3: Exchange Features (v1.1)

CREATE TABLE IF NOT EXISTS exchange_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_number INTEGER NOT NULL,
    exchange_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    note TEXT,
    color TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(rp_folder, branch, exchange_number),
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_rp_branch
    ON exchange_bookmarks(rp_folder, branch);

CREATE TABLE IF NOT EXISTS exchange_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    exchange_id INTEGER NOT NULL,
    exchange_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    annotation_type TEXT NOT NULL DEFAULT 'note',
    include_in_context INTEGER NOT NULL DEFAULT 0,
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
);

CREATE INDEX IF NOT EXISTS idx_annotations_exchange
    ON exchange_annotations(rp_folder, branch, exchange_number);

CREATE INDEX IF NOT EXISTS idx_annotations_type
    ON exchange_annotations(rp_folder, branch, annotation_type);
