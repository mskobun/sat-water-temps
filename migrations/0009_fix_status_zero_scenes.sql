-- Fix status computation: scenes_count = 0 should be 'completed' (no data),
-- not 'processing'. Only scenes_count IS NULL means still waiting.

DROP VIEW IF EXISTS ecostress_requests_with_status;

CREATE VIEW ecostress_requests_with_status AS
SELECT
  er.id,
  er.task_id,
  er.trigger_type,
  er.triggered_by,
  er.description,
  er.start_date,
  er.end_date,
  er.scenes_count,
  er.created_at,
  er.updated_at,
  er.error_message,
  er.dispatched_at,
  CASE
    WHEN er.task_id IS NULL THEN 'pending'
    WHEN (SELECT status FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'scrape' LIMIT 1) = 'failed' THEN 'failed'
    WHEN er.scenes_count IS NULL THEN 'processing'
    WHEN er.scenes_count = 0 THEN 'completed'
    WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status IN ('success', 'failed')) >= er.scenes_count THEN
      CASE
        WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'failed') > 0 THEN 'completed_with_errors'
        ELSE 'completed'
      END
    ELSE 'processing'
  END as status
FROM ecostress_requests er;
