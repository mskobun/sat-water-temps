-- Migration: Switch to hybrid architecture (D1 for metadata, R2 for data)
-- Drop temperature_data table (data stays in R2 CSVs)
-- Add R2 file paths and additional stats to metadata table

-- Drop the temperature_data table (no longer needed)
DROP TABLE IF EXISTS temperature_data;

-- Add new columns to temperature_metadata for hybrid architecture
ALTER TABLE temperature_metadata ADD COLUMN mean_temp REAL;
ALTER TABLE temperature_metadata ADD COLUMN median_temp REAL;
ALTER TABLE temperature_metadata ADD COLUMN std_dev REAL;
ALTER TABLE temperature_metadata ADD COLUMN water_pixel_count INTEGER;
ALTER TABLE temperature_metadata ADD COLUMN land_pixel_count INTEGER;
ALTER TABLE temperature_metadata ADD COLUMN csv_path TEXT;
ALTER TABLE temperature_metadata ADD COLUMN tif_path TEXT;
ALTER TABLE temperature_metadata ADD COLUMN png_path TEXT;
ALTER TABLE temperature_metadata ADD COLUMN created_at INTEGER;

-- Add index for faster metadata queries
CREATE INDEX IF NOT EXISTS idx_metadata_feature ON temperature_metadata(feature_id);
CREATE INDEX IF NOT EXISTS idx_metadata_date ON temperature_metadata(date);

-- Add index for job queries
CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON processing_jobs(job_type, status);
