-- Separate X (longitude) pixel size for non-square pixels (e.g. Landsat UTM→WGS84).
-- Existing pixel_size column becomes the Y (latitude) size.
ALTER TABLE temperature_metadata ADD COLUMN pixel_size_x REAL;
