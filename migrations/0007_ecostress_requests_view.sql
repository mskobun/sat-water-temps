-- Create view with computed status for ecostress_requests
-- This centralizes the status calculation logic in one place

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
  CASE
    WHEN er.task_id IS NULL THEN 'pending'
    WHEN (SELECT status FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'scrape' LIMIT 1) = 'failed' THEN 'failed'
    WHEN er.scenes_count IS NULL OR er.scenes_count = 0 THEN 'processing'
    WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status IN ('success', 'failed')) >= er.scenes_count THEN
      CASE
        WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'failed') > 0 THEN 'completed_with_errors'
        ELSE 'completed'
      END
    ELSE 'processing'
  END as status
FROM ecostress_requests er;
