-- 007_idempotency_key.sql: Add dedicated idempotency_key column to exchanges
--
-- Replaces the LIKE query on metadata JSON with a proper indexed column.

ALTER TABLE exchanges ADD COLUMN idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_exchanges_idempotency
    ON exchanges(rp_folder, branch, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Backfill from existing metadata JSON
UPDATE exchanges
SET idempotency_key = json_extract(metadata, '$.idempotency_key')
WHERE json_extract(metadata, '$.idempotency_key') IS NOT NULL;
