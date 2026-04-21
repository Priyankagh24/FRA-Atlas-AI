-- ============================================================
-- FRA Atlas — DB Migration for New Features
-- Run ONCE in your PostgreSQL client
-- ============================================================

-- 1. Add NER data column (stores raw NER entities as JSON for audit trail)
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS ner_data JSONB;

-- 2. Add claim_type column if missing (some older DBs may not have it)
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS claim_type TEXT;

-- 3. Add block column if missing
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS block TEXT;

-- 4. Add eligible_scheme column if missing
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS eligible_scheme TEXT;

-- 5. Add ml_land_use and ml_confidence columns if missing
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS ml_land_use TEXT;
ALTER TABLE fra_documents
  ADD COLUMN IF NOT EXISTS ml_confidence FLOAT;

-- 6. Indexes for DSS & progress queries (big performance boost)
CREATE INDEX IF NOT EXISTS idx_fra_state     ON fra_documents (LOWER(state));
CREATE INDEX IF NOT EXISTS idx_fra_district  ON fra_documents (LOWER(district));
CREATE INDEX IF NOT EXISTS idx_fra_village   ON fra_documents (LOWER(village_name));
CREATE INDEX IF NOT EXISTS idx_fra_scheme    ON fra_documents (LOWER(eligible_scheme));
CREATE INDEX IF NOT EXISTS idx_fra_land_use  ON fra_documents (LOWER(land_use));
CREATE INDEX IF NOT EXISTS idx_fra_claim_type ON fra_documents (LOWER(claim_type));

-- 7. Ensure schemes table has unique name constraint
ALTER TABLE schemes
  ADD CONSTRAINT IF NOT EXISTS schemes_name_unique UNIQUE (name);

-- ============================================================
-- Verify
-- ============================================================
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'fra_documents'
ORDER BY ordinal_position;