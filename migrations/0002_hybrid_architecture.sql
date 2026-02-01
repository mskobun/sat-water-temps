-- Migration: Switch to hybrid architecture (D1 for metadata, R2 for data)
-- Schema (temperature_metadata columns, indexes) is defined in 0001_init_schema.sql.
-- This migration only drops the legacy temperature_data table if it existed
-- from an older schema; no-op when 0001 was applied as the current full schema.
DROP TABLE IF EXISTS temperature_data;
