-- Seed default processing settings for the pipeline.
-- landsat_water_mask: controls which water mask is applied during Landsat processing.
--   "native"     = QA_PIXEL bit 7 (CFMask water flag)
--   "opera_dswx" = OPERA DSWx-HLS B01_WTR (purpose-built 30m water classification)
INSERT OR IGNORE INTO app_settings (key, value, updated_at)
VALUES ('landsat_water_mask', 'native', unixepoch());
