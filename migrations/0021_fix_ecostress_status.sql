-- Fix ECOSTRESS status view for STAC migration:
-- 1. job_type 'scrape' → 'ecostress_submit', 'process' → 'ecostress_process'
-- 2. Check error_message first (failed requests may have no task_id)
-- 3. Handle requests with scenes_count but no task_id (old data before synthetic task_ids)
-- 4. task_id IS NULL AND scenes_count IS NULL → 'pending' (manual triggers before Lambda runs)

DROP VIEW IF EXISTS data_requests_with_status;

CREATE VIEW data_requests_with_status AS
SELECT
  dr.*,
  CASE
    WHEN dr.source = 'ecostress' THEN
      CASE
        WHEN dr.error_message IS NOT NULL THEN 'failed'
        WHEN dr.scenes_count IS NOT NULL AND dr.scenes_count = 0 THEN 'completed'
        WHEN dr.task_id IS NOT NULL THEN
          CASE
            WHEN (SELECT status FROM processing_jobs pj
                  WHERE pj.task_id = dr.task_id AND pj.job_type = 'ecostress_submit' LIMIT 1) = 'failed'
              THEN 'failed'
            WHEN dr.scenes_count IS NULL THEN 'processing'
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
        -- No task_id: use scenes_count + date-range job matching for old data
        WHEN dr.scenes_count IS NOT NULL AND dr.scenes_count > 0 THEN
          CASE
            WHEN (SELECT COUNT(*) FROM processing_jobs pj
                  WHERE pj.job_type = 'ecostress_process'
                  AND pj.status IN ('success', 'failed', 'nodata')
                  AND pj.date >= dr.start_date || 'T00:00:00'
                  AND pj.date <= dr.end_date || 'T23:59:59'
                  AND pj.started_at >= dr.created_at) >= dr.scenes_count THEN
              CASE
                WHEN (SELECT COUNT(*) FROM processing_jobs pj
                      WHERE pj.job_type = 'ecostress_process'
                      AND pj.status = 'failed'
                      AND pj.date >= dr.start_date || 'T00:00:00'
                      AND pj.date <= dr.end_date || 'T23:59:59'
                      AND pj.started_at >= dr.created_at) > 0
                  THEN 'completed_with_errors'
                ELSE 'completed'
              END
            ELSE 'processing'
          END
        ELSE 'pending'
      END
    WHEN dr.source = 'landsat' THEN
      CASE
        WHEN dr.error_message IS NOT NULL THEN 'failed'
        WHEN dr.scenes_count IS NOT NULL AND dr.scenes_count > 0 THEN 'completed'
        ELSE 'pending'
      END
  END AS status
FROM data_requests dr;
