-- Composite index for active variant lookups (used by _increment_continue_count)
CREATE INDEX IF NOT EXISTS idx_variants_active ON exchange_variants(exchange_id, is_active);
