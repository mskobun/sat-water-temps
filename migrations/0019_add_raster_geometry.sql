-- Scene-level CRS and affine transform (rasterio order: a,b,c,d,e,f) for exact pixel quads.
-- Landsat: projected CRS + clipped transform. ECOSTRESS: WGS84 + geographic transform (nullable until backfill).
ALTER TABLE temperature_metadata ADD COLUMN source_crs TEXT;
ALTER TABLE temperature_metadata ADD COLUMN transform_a REAL;
ALTER TABLE temperature_metadata ADD COLUMN transform_b REAL;
ALTER TABLE temperature_metadata ADD COLUMN transform_c REAL;
ALTER TABLE temperature_metadata ADD COLUMN transform_d REAL;
ALTER TABLE temperature_metadata ADD COLUMN transform_e REAL;
ALTER TABLE temperature_metadata ADD COLUMN transform_f REAL;
