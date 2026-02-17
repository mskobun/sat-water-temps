-- Remove status column from ecostress_requests
-- Status is now computed dynamically from processing_jobs

-- SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
CREATE TABLE ecostress_requests_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT,
  trigger_type TEXT NOT NULL,
  triggered_by TEXT,
  description TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  scenes_count INTEGER,
  created_at INTEGER NOT NULL DEFAULT (unixepoch() * 1000),
  updated_at INTEGER,
  error_message TEXT
);

-- Copy data from old table
INSERT INTO ecostress_requests_new
SELECT id, task_id, trigger_type, triggered_by, description, start_date, end_date, scenes_count, created_at, updated_at, error_message
FROM ecostress_requests;

-- Drop old table
DROP TABLE ecostress_requests;

-- Rename new table
ALTER TABLE ecostress_requests_new RENAME TO ecostress_requests;

-- Recreate indexes
CREATE INDEX idx_ecostress_requests_created ON ecostress_requests(created_at);
CREATE INDEX idx_ecostress_requests_task_id ON ecostress_requests(task_id);
