-- 017_trust_source.sql: Add source column to trust_baselines
--
-- Tracks origin of each trust baseline:
--   'card'    — seeded from story card indexing (initial_relationships, npc_trust_levels)
--   'runtime' — created by gameplay (update_trust) or branch snapshot
ALTER TABLE trust_baselines ADD COLUMN source TEXT DEFAULT 'runtime';
