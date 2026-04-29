-- Add per-job filter_stats column so each processing_jobs row has an immutable
-- snapshot of the filter stats from when it ran. Previously filter_stats came
-- from a JOIN on temperature_metadata, which uses INSERT OR REPLACE — meaning
-- a reprocess would silently update the filter_stats of all historic jobs for
-- the same feature+date.
ALTER TABLE processing_jobs ADD COLUMN filter_stats TEXT;

-- Backfill: copy the current temperature_metadata.filter_stats into success jobs.
-- Best-effort: only one snapshot exists per feature+date but it beats nothing.
UPDATE processing_jobs
SET filter_stats = (
    SELECT tm.filter_stats
    FROM temperature_metadata tm
    WHERE tm.feature_id = processing_jobs.feature_id
      AND tm.date = processing_jobs.date
)
WHERE status = 'success'
  AND filter_stats IS NULL;
