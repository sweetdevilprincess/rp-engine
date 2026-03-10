-- Add archive support to branches
ALTER TABLE branches ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
