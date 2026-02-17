-- Add filter_stats column to temperature_metadata table
-- Stores JSON with filter statistics (QC, cloud, water breakdown)
ALTER TABLE temperature_metadata ADD COLUMN filter_stats TEXT;
