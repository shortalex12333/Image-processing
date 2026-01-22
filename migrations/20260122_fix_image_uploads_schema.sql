-- Migration: Fix pms_image_uploads schema - add ALL missing columns
-- Date: 2026-01-22
-- Purpose: Add missing core columns + OCR columns to make table match code expectations
-- Author: Claude Sonnet 4.5

-- CRITICAL: This table was created with incomplete schema
-- Current columns: yacht_id, uploaded_by, file_name, mime_type, file_size_bytes,
--                  storage_path, metadata, uploaded_at, created_at, updated_at, processed_at

-- Add PRIMARY KEY column (critical!)
ALTER TABLE pms_image_uploads
  ADD COLUMN IF NOT EXISTS image_id uuid PRIMARY KEY DEFAULT gen_random_uuid();

-- Add core missing columns for image upload workflow
ALTER TABLE pms_image_uploads
  ADD COLUMN IF NOT EXISTS sha256 text,
  ADD COLUMN IF NOT EXISTS processing_status text DEFAULT 'queued',
  ADD COLUMN IF NOT EXISTS width integer,
  ADD COLUMN IF NOT EXISTS height integer,
  ADD COLUMN IF NOT EXISTS blur_score float;

-- Add OCR result columns
ALTER TABLE pms_image_uploads
  ADD COLUMN IF NOT EXISTS ocr_text text,
  ADD COLUMN IF NOT EXISTS ocr_confidence float,
  ADD COLUMN IF NOT EXISTS ocr_engine text,
  ADD COLUMN IF NOT EXISTS ocr_processing_time_ms integer,
  ADD COLUMN IF NOT EXISTS ocr_line_count integer,
  ADD COLUMN IF NOT EXISTS ocr_word_count integer,
  ADD COLUMN IF NOT EXISTS extracted_entities jsonb;

-- Create indexes for performance and deduplication
CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_yacht_id
  ON pms_image_uploads(yacht_id);

CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_sha256
  ON pms_image_uploads(sha256);

CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_processing_status
  ON pms_image_uploads(processing_status);

CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_processed_at
  ON pms_image_uploads(processed_at);

CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_ocr_engine
  ON pms_image_uploads(ocr_engine);

-- Full-text search on OCR text
CREATE INDEX IF NOT EXISTS idx_pms_image_uploads_ocr_text
  ON pms_image_uploads
  USING gin(to_tsvector('english', ocr_text));

-- Add constraints (skip IF NOT EXISTS - not supported in older PostgreSQL)
-- Constraint will be added if it doesn't exist, error ignored if it does
DO $$
BEGIN
  ALTER TABLE pms_image_uploads
    ADD CONSTRAINT chk_processing_status
    CHECK (processing_status IN ('queued', 'processing', 'completed', 'failed'));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Make sha256 unique per yacht (deduplication)
CREATE UNIQUE INDEX IF NOT EXISTS idx_pms_image_uploads_yacht_sha256
  ON pms_image_uploads(yacht_id, sha256)
  WHERE sha256 IS NOT NULL;

-- Add column comments
COMMENT ON COLUMN pms_image_uploads.image_id IS 'Primary key - unique image identifier';
COMMENT ON COLUMN pms_image_uploads.sha256 IS 'SHA256 hash for deduplication';
COMMENT ON COLUMN pms_image_uploads.processing_status IS 'queued, processing, completed, or failed';
COMMENT ON COLUMN pms_image_uploads.width IS 'Image width in pixels';
COMMENT ON COLUMN pms_image_uploads.height IS 'Image height in pixels';
COMMENT ON COLUMN pms_image_uploads.blur_score IS 'Blur detection score (0-1, higher = less blurry)';
COMMENT ON COLUMN pms_image_uploads.ocr_text IS 'Raw OCR extracted text (for audit/debugging)';
COMMENT ON COLUMN pms_image_uploads.ocr_confidence IS 'Average OCR confidence score (0.0-1.0)';
COMMENT ON COLUMN pms_image_uploads.ocr_engine IS 'OCR engine used (paddleocr, tesseract, etc.)';
COMMENT ON COLUMN pms_image_uploads.ocr_processing_time_ms IS 'OCR processing time in milliseconds';
COMMENT ON COLUMN pms_image_uploads.ocr_line_count IS 'Number of text lines extracted';
COMMENT ON COLUMN pms_image_uploads.ocr_word_count IS 'Number of words extracted';
COMMENT ON COLUMN pms_image_uploads.extracted_entities IS 'JSON with order_number, tracking_numbers, supplier, etc.';
COMMENT ON COLUMN pms_image_uploads.processed_at IS 'Timestamp when OCR processing completed';

-- Create database views for monitoring

-- View: Recent OCR results with statistics
CREATE OR REPLACE VIEW vw_recent_ocr_results AS
SELECT
  iu.image_id,
  iu.yacht_id,
  iu.file_name,
  iu.ocr_engine,
  iu.ocr_confidence,
  iu.ocr_word_count,
  iu.ocr_processing_time_ms,
  iu.processing_status,
  iu.uploaded_at,
  iu.processed_at,
  (EXTRACT(EPOCH FROM (iu.processed_at - iu.uploaded_at)) * 1000)::integer as total_processing_time_ms
FROM pms_image_uploads iu
WHERE iu.ocr_text IS NOT NULL
ORDER BY iu.processed_at DESC;

-- View: OCR quality metrics (for monitoring)
CREATE OR REPLACE VIEW vw_ocr_quality_metrics AS
SELECT
  yacht_id,
  ocr_engine,
  COUNT(*) as total_images,
  ROUND(AVG(ocr_confidence)::numeric, 4) as avg_confidence,
  ROUND(MIN(ocr_confidence)::numeric, 4) as min_confidence,
  ROUND(MAX(ocr_confidence)::numeric, 4) as max_confidence,
  ROUND(AVG(ocr_processing_time_ms)::numeric, 2) as avg_processing_time_ms,
  ROUND(AVG(ocr_word_count)::numeric, 2) as avg_word_count,
  DATE_TRUNC('day', MIN(processed_at)) as first_processed,
  DATE_TRUNC('day', MAX(processed_at)) as last_processed
FROM pms_image_uploads
WHERE ocr_text IS NOT NULL
GROUP BY yacht_id, ocr_engine
ORDER BY yacht_id, ocr_engine;

-- View: Low confidence OCR results (for manual review)
CREATE OR REPLACE VIEW vw_low_confidence_ocr AS
SELECT
  iu.image_id,
  iu.yacht_id,
  iu.file_name,
  iu.ocr_engine,
  iu.ocr_confidence,
  iu.ocr_word_count,
  iu.storage_path,
  iu.processed_at
FROM pms_image_uploads iu
WHERE iu.ocr_confidence < 0.7
  AND iu.ocr_text IS NOT NULL
ORDER BY iu.ocr_confidence ASC;

-- View: Upload statistics by yacht
CREATE OR REPLACE VIEW vw_image_upload_stats AS
SELECT
  yacht_id,
  COUNT(*) as total_uploads,
  COUNT(DISTINCT sha256) as unique_images,
  COUNT(*) - COUNT(DISTINCT sha256) as duplicates,
  SUM(file_size_bytes) as total_bytes,
  AVG(file_size_bytes) as avg_file_size,
  COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
  COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed,
  COUNT(CASE WHEN processing_status = 'queued' THEN 1 END) as queued,
  MIN(uploaded_at) as first_upload,
  MAX(uploaded_at) as last_upload
FROM pms_image_uploads
GROUP BY yacht_id;

COMMENT ON VIEW vw_recent_ocr_results IS 'Shows recent OCR results with processing time statistics';
COMMENT ON VIEW vw_ocr_quality_metrics IS 'Aggregated OCR quality metrics by yacht and engine';
COMMENT ON VIEW vw_low_confidence_ocr IS 'OCR results with confidence below 70% requiring manual review';
COMMENT ON VIEW vw_image_upload_stats IS 'Upload statistics and deduplication metrics by yacht';

-- Grant appropriate permissions (if using RLS)
-- ALTER TABLE pms_image_uploads ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY IF NOT EXISTS "Users can view own yacht images"
--   ON pms_image_uploads FOR SELECT
--   USING (yacht_id = (current_setting('app.current_yacht_id')::uuid));
