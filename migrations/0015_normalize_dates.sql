-- Normalize all dates to ISO datetime format (YYYY-MM-DDTHH:MM:SS).
-- ECOSTRESS DOY "2024362041923" → "2024-12-27T04:19:23"
-- Landsat ISO  "2024-12-27"     → "2024-12-27T00:00:00"

-- temperature_metadata: convert Landsat ISO dates (10 chars with hyphen at pos 5)
UPDATE temperature_metadata
SET date = date || 'T00:00:00'
WHERE length(date) = 10 AND substr(date, 5, 1) = '-';

-- temperature_metadata: convert ECOSTRESS DOY dates (13 chars, no hyphen at pos 5)
UPDATE temperature_metadata
SET date = date(
    substr(date, 1, 4) || '-01-01',
    '+' || (CAST(substr(date, 5, 3) AS INTEGER) - 1) || ' days'
  ) || 'T' ||
  substr(date, 8, 2) || ':' ||
  substr(date, 10, 2) || ':' ||
  substr(date, 12, 2)
WHERE length(date) = 13 AND substr(date, 5, 1) != '-';

-- processing_jobs: convert Landsat ISO dates
UPDATE processing_jobs
SET date = date || 'T00:00:00'
WHERE date IS NOT NULL
  AND length(date) = 10 AND substr(date, 5, 1) = '-';

-- processing_jobs: convert ECOSTRESS DOY dates
UPDATE processing_jobs
SET date = date(
    substr(date, 1, 4) || '-01-01',
    '+' || (CAST(substr(date, 5, 3) AS INTEGER) - 1) || ' days'
  ) || 'T' ||
  substr(date, 8, 2) || ':' ||
  substr(date, 10, 2) || ':' ||
  substr(date, 12, 2)
WHERE date IS NOT NULL
  AND length(date) = 13 AND substr(date, 5, 1) != '-';

-- features.latest_date: convert Landsat ISO dates
UPDATE features
SET latest_date = latest_date || 'T00:00:00'
WHERE latest_date IS NOT NULL
  AND length(latest_date) = 10 AND substr(latest_date, 5, 1) = '-';

-- features.latest_date: convert ECOSTRESS DOY dates
UPDATE features
SET latest_date = date(
    substr(latest_date, 1, 4) || '-01-01',
    '+' || (CAST(substr(latest_date, 5, 3) AS INTEGER) - 1) || ' days'
  ) || 'T' ||
  substr(latest_date, 8, 2) || ':' ||
  substr(latest_date, 10, 2) || ':' ||
  substr(latest_date, 12, 2)
WHERE latest_date IS NOT NULL
  AND length(latest_date) = 13 AND substr(latest_date, 5, 1) != '-';

-- Drop latest_sort_date since all dates now sort correctly as ISO strings
ALTER TABLE features DROP COLUMN latest_sort_date;
