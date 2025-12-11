-- Migration: Hybrid architecture - D1 for metadata/jobs, R2 for temperature data
-- This keeps D1 within free tier limits while maintaining fast metadata queries

-- Features table: Basic feature info and latest date
CREATE TABLE IF NOT EXISTS features (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT DEFAULT 'lake',
  latest_date TEXT,
  last_updated INTEGER
);

-- Metadata table: Stats per date with R2 file paths
-- Temperature point data (CSV) stays in R2, only metadata in D1
CREATE TABLE IF NOT EXISTS temperature_metadata (
  feature_id TEXT NOT NULL,
  date TEXT NOT NULL,
  min_temp REAL,
  max_temp REAL,
  mean_temp REAL,
  median_temp REAL,
  std_dev REAL,
  data_points INTEGER,
  water_pixel_count INTEGER,
  land_pixel_count INTEGER,
  wtoff BOOLEAN DEFAULT 0,
  csv_path TEXT, -- R2 path: {feature_id}/csv/{date}.csv
  tif_path TEXT, -- R2 path: {feature_id}/tif/{date}.tif
  png_path TEXT, -- R2 path: {feature_id}/png/{date}.png
  created_at INTEGER DEFAULT (unixepoch()),
  PRIMARY KEY (feature_id, date),
  FOREIGN KEY (feature_id) REFERENCES features(id)
);
CREATE INDEX IF NOT EXISTS idx_metadata_feature ON temperature_metadata(feature_id);
CREATE INDEX IF NOT EXISTS idx_metadata_date ON temperature_metadata(date);

-- Processing jobs table: Lambda job tracking and monitoring
CREATE TABLE IF NOT EXISTS processing_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_type TEXT NOT NULL, -- 'scrape' or 'process'
  task_id TEXT,
  feature_id TEXT,
  date TEXT,
  status TEXT NOT NULL, -- 'started', 'success', 'failed'
  started_at INTEGER NOT NULL,
  completed_at INTEGER,
  duration_ms INTEGER,
  error_message TEXT,
  metadata TEXT -- JSON for additional info
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_date ON processing_jobs(status, started_at);
CREATE INDEX IF NOT EXISTS idx_jobs_feature_date ON processing_jobs(feature_id, date);
CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON processing_jobs(job_type, status);

