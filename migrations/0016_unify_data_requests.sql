-- Unify ecostress_requests and landsat_runs into a single data_requests table.

CREATE TABLE data_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,                -- 'ecostress' or 'landsat'
  task_id TEXT,                        -- AppEEARS task_id (ECOSTRESS only)
  trigger_type TEXT NOT NULL DEFAULT 'timer',
  triggered_by TEXT,
  description TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  scenes_count INTEGER,                -- ecostress scenes_count / landsat scenes_submitted
  created_at INTEGER NOT NULL DEFAULT (unixepoch() * 1000),
  updated_at INTEGER,
  dispatched_at INTEGER,               -- ECOSTRESS task_poller only
  error_message TEXT
);

CREATE INDEX idx_data_requests_source ON data_requests(source);
CREATE INDEX idx_data_requests_created ON data_requests(created_at);
CREATE INDEX idx_data_requests_task_id ON data_requests(task_id);

-- Migrate ecostress_requests data
INSERT INTO data_requests (id, source, task_id, trigger_type, triggered_by, description,
    start_date, end_date, scenes_count, created_at, updated_at, dispatched_at, error_message)
SELECT id, 'ecostress', task_id, trigger_type, triggered_by, description,
    start_date, end_date, scenes_count, created_at, updated_at, dispatched_at, error_message
FROM ecostress_requests;

-- Migrate landsat_runs data (IDs will auto-increment past ecostress IDs)
INSERT INTO data_requests (source, trigger_type, triggered_by, description,
    start_date, end_date, scenes_count, created_at, updated_at, error_message)
SELECT 'landsat', trigger_type, triggered_by, description,
    start_date, end_date, scenes_submitted, created_at, updated_at, error_message
FROM landsat_runs;

-- Drop old computed status view
DROP VIEW IF EXISTS ecostress_requests_with_status;

-- Create unified status view
CREATE VIEW data_requests_with_status AS
SELECT
  dr.*,
  CASE
    WHEN dr.source = 'ecostress' THEN
      CASE
        WHEN dr.task_id IS NULL THEN 'pending'
        WHEN (SELECT status FROM processing_jobs pj
              WHERE pj.task_id = dr.task_id AND pj.job_type = 'scrape' LIMIT 1) = 'failed'
          THEN 'failed'
        WHEN dr.scenes_count IS NULL THEN 'processing'
        WHEN dr.scenes_count = 0 THEN 'completed'
        WHEN (SELECT COUNT(*) FROM processing_jobs pj
              WHERE pj.task_id = dr.task_id AND pj.job_type = 'process'
              AND pj.status IN ('success', 'failed')) >= dr.scenes_count THEN
          CASE
            WHEN (SELECT COUNT(*) FROM processing_jobs pj
                  WHERE pj.task_id = dr.task_id AND pj.job_type = 'process'
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

-- Drop old tables
DROP TABLE IF EXISTS ecostress_requests;
DROP TABLE IF EXISTS landsat_runs;
