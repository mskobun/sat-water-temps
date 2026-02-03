-- Track ECOSTRESS/AppEEARS requests with trigger metadata
CREATE TABLE ecostress_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT UNIQUE,
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

CREATE INDEX idx_ecostress_requests_status ON ecostress_requests(status);
CREATE INDEX idx_ecostress_requests_created ON ecostress_requests(created_at);
CREATE INDEX idx_ecostress_requests_task_id ON ecostress_requests(task_id);
