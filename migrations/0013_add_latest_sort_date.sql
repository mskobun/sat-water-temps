-- Add sortable ISO date column to features for correct chronological comparison
-- across ECOSTRESS DOY ("2024362041923") and Landsat ISO ("2024-12-27") formats.
ALTER TABLE features ADD COLUMN latest_sort_date TEXT;
