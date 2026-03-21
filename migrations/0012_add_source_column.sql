-- Add source column to temperature_metadata to distinguish ECOSTRESS vs Landsat data
ALTER TABLE temperature_metadata ADD COLUMN source TEXT NOT NULL DEFAULT 'ecostress';

-- Landsat run tracking (mirrors ecostress_requests)
CREATE TABLE IF NOT EXISTS landsat_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_type TEXT NOT NULL DEFAULT 'timer',
    triggered_by TEXT,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    scenes_submitted INTEGER,
    created_at INTEGER,
    updated_at INTEGER,
    error_message TEXT
);
