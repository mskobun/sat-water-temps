-- Drop the legacy `wtoff` (water-turn-off) column from temperature_metadata.
-- Scenes with no detected water are now rejected as nodata by the processors;
-- run the `backfill:wtoff` handler BEFORE applying this migration to clean up
-- existing wtoff=1 rows and their R2 / parquet artifacts.

ALTER TABLE temperature_metadata DROP COLUMN wtoff;
