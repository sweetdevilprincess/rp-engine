-- Add branch column to card_gaps for branch isolation.
-- SQLite can't ALTER PRIMARY KEY, so recreate the table.
CREATE TABLE IF NOT EXISTS card_gaps_new (
    entity_name TEXT NOT NULL,
    rp_folder TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'main',
    suggested_type TEXT,
    seen_count INTEGER DEFAULT 1,
    first_seen TEXT,
    last_seen TEXT,
    PRIMARY KEY (entity_name, rp_folder, branch)
);

INSERT OR IGNORE INTO card_gaps_new
    SELECT entity_name, rp_folder, 'main', suggested_type, seen_count, first_seen, last_seen
    FROM card_gaps;

DROP TABLE IF EXISTS card_gaps;
ALTER TABLE card_gaps_new RENAME TO card_gaps;
