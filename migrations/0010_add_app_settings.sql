CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at INTEGER
);

INSERT OR IGNORE INTO app_settings (key, value, updated_at)
  VALUES ('data_delay_days', '2', strftime('%s','now') * 1000);
