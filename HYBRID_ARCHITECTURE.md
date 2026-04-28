# Hybrid Architecture: D1 + R2

## Overview

The project uses a hybrid storage model:

- **D1** — small, frequently-queried metadata and job/request state
- **R2** — large per-observation data files (CSV, Parquet, TIF, PNG)

## Why

Large features can have 200 000+ temperature points per observation. Storing those in D1 would hit the free-tier write quota within a day. R2 is designed for bulk file storage and scales without issue. D1 stays thin (a few hundred rows per day) and fast for metadata queries.

## D1 tables

### `features`
One row per monitored water body.

| column | type | notes |
|--------|------|-------|
| id | TEXT PK | feature name slug |
| name | TEXT | display name |
| location | TEXT | default `lake` |
| latest_date | TEXT | most recent observation date |
| last_updated | INTEGER | unix timestamp |

### `temperature_metadata`
One row per (feature, date, source) observation.

| column | type | notes |
|--------|------|-------|
| feature_id | TEXT | FK → features.id |
| date | TEXT | ISO 8601 |
| source | TEXT | `ecostress` or `landsat` |
| min_temp / max_temp / mean_temp / median_temp / std_dev | REAL | Kelvin |
| data_points | INTEGER | valid water pixels |
| water_pixel_count / land_pixel_count | INTEGER | |
| filter_stats | TEXT | JSON histogram of QC/cloud/water/nodata flag counts |
| csv_path | TEXT | R2 key for gzip-compressed CSV |
| tif_path | TEXT | R2 key for GeoTIFF |
| png_path | TEXT | R2 key base — append `_{scale}.png` |
| parquet_path | TEXT | R2 key for Parquet file |
| pixel_size | REAL | Y (latitude) pixel spacing in degrees |
| pixel_size_x | REAL | X (longitude) pixel spacing in degrees |
| source_crs | TEXT | WKT CRS string (Landsat: projected UTM; ECOSTRESS: WGS84) |
| transform_a–f | REAL | Affine coefficients (rasterio order) for pixel-exact quad rendering |
| created_at | INTEGER | unix timestamp |

### `processing_jobs`
Lambda job tracking.

| column | type | notes |
|--------|------|-------|
| id | INTEGER PK | |
| job_type | TEXT | `scrape` or `process` |
| task_id | TEXT | links to data_requests |
| feature_id / date | TEXT | |
| status | TEXT | `started`, `success`, `failed`, `nodata` |
| started_at / completed_at / duration_ms | INTEGER | |
| error_message | TEXT | |
| metadata | TEXT | JSON for extra context |

### `data_requests`
One row per manual or scheduled ingest run.

| column | type | notes |
|--------|------|-------|
| id | INTEGER PK | |
| source | TEXT | `ecostress` or `landsat` |
| trigger_type | TEXT | `timer` or `manual` |
| triggered_by / description | TEXT | |
| start_date / end_date | TEXT | requested date range |
| scenes_count | INTEGER | scenes dispatched |
| task_id | TEXT | ECOSTRESS AppEEARS task ID (if applicable) |
| created_at / updated_at / dispatched_at | INTEGER | |
| error_message | TEXT | |

### `data_requests_with_status` (view)
Joins `data_requests` with `processing_jobs` to compute a derived `status` field per request.

### `app_settings`
Key/value store for runtime config. Current keys: `data_delay_days`.

## R2 storage structure

All files live in the `multitifs` bucket. Keys follow source-specific prefixes:

```
ECO/{feature_name}/{location}/{feature_name}_{location}_{date}_filter.csv.gz
ECO/{feature_name}/{location}/{feature_name}_{location}_{date}_filter.tif
ECO/{feature_name}/{location}/{feature_name}_{location}_{date}_filter_{scale}.png
ECO/{feature_name}/{location}/{feature_name}_{location}.parquet

LANDSAT/{feature_name}/{location}/{feature_name}_{location}_{date}_filter.csv.gz
LANDSAT/{feature_name}/{location}/{feature_name}_{location}_{date}_filter.tif
LANDSAT/{feature_name}/{location}/{feature_name}_{location}_{date}_filter_{scale}.png
LANDSAT/{feature_name}/{location}/{feature_name}_{location}.parquet
```

`{scale}` is `relative`, `fixed`, or `gray` depending on which PNG variants were generated.

CSVs are gzip-compressed and uploaded with `ContentEncoding: gzip` so R2 transparently decompresses them on read. See [docs/R2_GZIP_BEHAVIOR.md](docs/R2_GZIP_BEHAVIOR.md) for details.

## Data flow

### Ingestion (Lambda)

1. Initiator discovers scenes via CMR-STAC (ECOSTRESS) or USGS STAC (Landsat)
2. Sends per-feature/per-date SQS messages
3. Processor downloads raster, computes temperature stats, generates outputs
4. Uploads CSV.gz, TIF, PNG, and Parquet to R2
5. Inserts one `temperature_metadata` row to D1
6. Logs job status to `processing_jobs`

Key files: `lambda_functions/ecostress/processor.py`, `lambda_functions/landsat/processor.py`, `lambda_functions/common/metadata.py`

### API request (SvelteKit → client)

1. API routes query D1 for metadata (fast, indexed)
2. For point data, the API lists available Parquet file keys from D1
3. The browser fetches Parquet files directly and queries them with DuckDB WASM (`src/lib/duckdb-cache.ts`)
4. The map overlay renders pixel quads using the affine transform and CRS stored in D1

Key files: `src/lib/db.ts`, `src/routes/api/feature/[...id]/parquet/+server.ts`, `src/lib/duckdb-cache.ts`, `src/lib/deck-temperature-overlay.ts`

## Key files

| file | purpose |
|------|---------|
| `src/lib/db.ts` | D1 query helpers used by API routes |
| `src/lib/duckdb-cache.ts` | Client-side DuckDB WASM Parquet loader and query cache |
| `src/lib/deck-temperature-overlay.ts` | Map pixel quad rendering with affine transforms |
| `lambda_functions/common/metadata.py` | `insert_metadata_to_d1()` — writes D1 row after processing |
| `lambda_functions/common/storage.py` | R2 upload/download via boto3 S3 API |
| `migrations/` | Full D1 schema history |
