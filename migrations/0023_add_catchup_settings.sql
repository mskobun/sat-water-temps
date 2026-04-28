INSERT OR IGNORE INTO app_settings (key, value, updated_at)
  VALUES ('catchup_enabled', 'true', strftime('%s','now') * 1000);

INSERT OR IGNORE INTO app_settings (key, value, updated_at)
  VALUES ('catchup_overlap_days', '3', strftime('%s','now') * 1000);

INSERT OR IGNORE INTO app_settings (key, value, updated_at)
  VALUES ('catchup_max_days', '21', strftime('%s','now') * 1000);
