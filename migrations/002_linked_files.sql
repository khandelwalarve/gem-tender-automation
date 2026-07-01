-- migrations/002_linked_files.sql
-- Adds source_url to tender_files so we can distinguish
-- directly downloaded GeM attachments from externally linked files.

ALTER TABLE tender_files ADD COLUMN IF NOT EXISTS source_url TEXT DEFAULT NULL;
ALTER TABLE tender_files ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT 'attachment';
-- file_type: 'attachment' (direct from GeM) | 'linked' (discovered via URL in a document)

-- Unique constraint to prevent re-downloading the same linked file.
CREATE UNIQUE INDEX IF NOT EXISTS idx_tender_files_hash_per_tender
ON tender_files (tender_id, file_hash);
