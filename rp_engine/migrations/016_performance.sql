-- Migration 016: Performance optimizations
-- SCAN-01: Add always_load column to story_cards for SQL-level filtering

ALTER TABLE story_cards ADD COLUMN always_load BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_story_cards_always_load
    ON story_cards(rp_folder, always_load) WHERE always_load = 1;
