-- Drop unused tables superseded by extracted_memories (006).
-- These tables were created in 003_ledger_cow.sql but never used in production code.
DROP TABLE IF EXISTS memory_entries;
DROP TABLE IF EXISTS knowledge_entries;
DROP TABLE IF EXISTS secret_events;
