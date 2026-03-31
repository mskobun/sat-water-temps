-- Fix ECOSTRESS status view for STAC migration:
-- 1. job_type 'scrape' → 'ecostress_submit', 'process' → 'ecostress_process'
-- 2. Check error_message first (failed requests may have no task_id)
-- 3. Check scenes_count before task_id (completed requests may predate synthetic task_ids)

DROP VIEW IF EXISTS data_requests_with_status;

CREATE VIEW data_requests_with_status AS
SELECT
  dr.*,
  CASE
    WHEN dr.source = 'ecostress' THEN
      CASE
        WHEN dr.error_message IS NOT NULL THEN 'failed'
        WHEN dr.task_id IS NULL AND dr.scenes_count IS NULL THEN 'pending'
        WHEN (SELECT status FROM processing_jobs pj
              WHERE pj.task_id = dr.task_id AND pj.job_type = 'ecostress_submit' LIMIT 1) = 'failed'
          THEN 'failed'
        WHEN dr.scenes_count IS NULL THEN 'processing'
        WHEN dr.scenes_count = 0 THEN 'completed'
        WHEN (SELECT COUNT(*) FROM processing_jobs pj
              WHERE pj.task_id = dr.task_id AND pj.job_type = 'ecostress_process'
              AND pj.status IN ('success', 'failed', 'nodata')) >= dr.scenes_count THEN
          CASE
            WHEN (SELECT COUNT(*) FROM processing_jobs pj
                  WHERE pj.task_id = dr.task_id AND pj.job_type = 'ecostress_process'
                  AND pj.status = 'failed') > 0
              THEN 'completed_with_errors'
            ELSE 'completed'
          END
        ELSE 'processing'
      END
    WHEN dr.source = 'landsat' THEN
      CASE
        WHEN dr.error_message IS NOT NULL THEN 'failed'
        WHEN dr.scenes_count IS NOT NULL AND dr.scenes_count > 0 THEN 'completed'
        ELSE 'pending'
      END
  END AS status
FROM data_requests dr;
