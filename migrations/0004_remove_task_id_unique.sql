-- Remove UNIQUE constraint from task_id to allow reprocessing
-- SQLite doesn't support ALTER TABLE DROP CONSTRAINT, so we need to recreate the table

-- Create new table without UNIQUE constraint on task_id
CREATE TABLE ecostress_requests_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT,
  trigger_type TEXT NOT NULL,
  triggered_by TEXT,
  description TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  scenes_count INTEGER,
  created_at INTEGER NOT NULL DEFAULT (unixepoch() * 1000),
  updated_at INTEGER,
  error_message TEXT
);

-- Copy data from old table
INSERT INTO ecostress_requests_new
SELECT * FROM ecostress_requests;

-- Drop old table
DROP TABLE ecostress_requests;

-- Rename new table
ALTER TABLE ecostress_requests_new RENAME TO ecostress_requests;

-- Recreate indexes (task_id no longer unique)
CREATE INDEX idx_ecostress_requests_status ON ecostress_requests(status);
CREATE INDEX idx_ecostress_requests_created ON ecostress_requests(created_at);
CREATE INDEX idx_ecostress_requests_task_id ON ecostress_requests(task_id);
