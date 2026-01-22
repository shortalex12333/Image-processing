-- Migration: Add OCR result columns to pms_image_uploads table
-- Date: 2026-01-22
-- Purpose: Store OCR results for audit trail and debugging
-- Author: Claude Sonnet 4.5

-- Add OCR result columns to pms_image_uploads table
ALTER TABLE pms_image_uploads
  ADD COLUMN ocr_text text,
  ADD COLUMN ocr_confidence float,
  ADD COLUMN ocr_engine text,
  ADD COLUMN ocr_processing_time_ms integer,
  ADD COLUMN ocr_line_count integer,
  ADD COLUMN ocr_word_count integer,
  ADD COLUMN extracted_entities jsonb,
  ADD COLUMN processed_at timestamp with time zone;

-- Add index for searching OCR text (full-text search)
CREATE INDEX idx_pms_image_uploads_ocr_text
  ON pms_image_uploads
  USING gin(to_tsvector('english', ocr_text));

-- Add index for processed_at (for time-based queries)
CREATE INDEX idx_pms_image_uploads_processed_at
  ON pms_image_uploads(processed_at);

-- Add index for ocr_engine (for filtering by engine type)
CREATE INDEX idx_pms_image_uploads_ocr_engine
  ON pms_image_uploads(ocr_engine);

-- Comment the columns for documentation
COMMENT ON COLUMN pms_image_uploads.ocr_text IS 'Raw OCR extracted text (for audit/debugging)';
COMMENT ON COLUMN pms_image_uploads.ocr_confidence IS 'Average OCR confidence score (0.0-1.0)';
COMMENT ON COLUMN pms_image_uploads.ocr_engine IS 'OCR engine used (paddleocr, tesseract, etc.)';
COMMENT ON COLUMN pms_image_uploads.ocr_processing_time_ms IS 'OCR processing time in milliseconds';
COMMENT ON COLUMN pms_image_uploads.ocr_line_count IS 'Number of text lines extracted';
COMMENT ON COLUMN pms_image_uploads.ocr_word_count IS 'Number of words extracted';
COMMENT ON COLUMN pms_image_uploads.extracted_entities IS 'JSON with order_number, tracking_numbers, supplier, etc.';
COMMENT ON COLUMN pms_image_uploads.processed_at IS 'Timestamp when OCR processing completed';

-- Create database views for easy querying

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

COMMENT ON VIEW vw_recent_ocr_results IS 'Shows recent OCR results with processing time statistics';
COMMENT ON VIEW vw_ocr_quality_metrics IS 'Aggregated OCR quality metrics by yacht and engine';
COMMENT ON VIEW vw_low_confidence_ocr IS 'OCR results with confidence below 70% requiring manual review';
