-- Pixel spacing in degrees (WGS84) for map heatmap squares; computed at ingest.
ALTER TABLE temperature_metadata ADD COLUMN pixel_size REAL;
