# Hybrid Architecture: D1 + R2

## Overview

This project uses a **hybrid storage architecture** to optimize costs and performance:

- **D1**: Small, frequently-queried metadata and job tracking
- **R2**: Large, static temperature data files

## Why Hybrid?

### The Problem
Initially, we attempted to store all temperature data in D1. However:
- Large features like "Bay" have **207,800+ temperature points per date**
- 49 features × 2 dates × ~50k avg points = **~5 million rows**
- D1 free tier: **100,000 rows written/day**
- **Migration would take 50+ days and blow through quotas immediately**

### The Solution
Keep temperature CSVs in R2, use D1 only for metadata:
- ✅ Stays well within D1 free tier (few hundred rows per day)
- ✅ R2 is designed for large static files
- ✅ CSVs are already optimized for the data structure
- ✅ Faster queries (no need to reconstruct large datasets)

## Architecture

### D1 Tables

#### `features`
- Basic feature information
- Latest available date
- ~49 rows total

#### `temperature_metadata`
- Statistics per date (min/max/mean temps)
- Water/land pixel counts
- **R2 file paths** (csv_path, tif_path, png_path)
- ~100 rows per feature (49 features × ~10 dates = ~500 rows)

#### `processing_jobs`
- Lambda job tracking
- Success/failure status
- Error messages for debugging
- ~10-50 new rows per day

**Total D1 usage**: ~1,000 rows + ~50 rows/day = **Well within free tier**

### R2 Storage Structure

```
multitifs/
├── {feature_id}/
│   ├── csv/
│   │   └── {date}.csv          # Temperature point data (can be 200k+ rows)
│   ├── tif/
│   │   └── {date}.tif          # Geospatial raster
│   └── png/
│       └── {date}.png          # Visualization
```

## Data Flow

### Processing (Lambda)
1. Lambda downloads Landsat data
2. Processes temperature raster → CSV
3. **Uploads CSV to R2** (large file)
4. Calculates statistics (min/max/mean)
5. **Inserts metadata to D1** (small row with file paths)
6. **Logs job status to D1**

### API Request (SvelteKit)
1. Frontend requests temperature **metadata** (JSON) and **points** (binary) for feature + date in parallel
2. **SvelteKit queries D1** for metadata and CSV path
3. **SvelteKit fetches CSV from R2** using path (once per endpoint; each request may parse CSV separately)
4. Metadata route returns sidebar/chart fields only; `/points` returns packed `Float32` triplets (`lng`, `lat`, `temperature`) with no JSON parse on the client for the large array

**Payload comparison:** binary points are **12 bytes per observation** (3× float32) vs. JSON triplets which are much larger on the wire and require `JSON.parse` plus nested array allocation. Use browser DevTools **Network** (transfer size and time) to compare before/after when tuning.

## File Reference

### Schema
- `migrations/0001_init_schema.sql` - D1 tables (no temperature_data table)

### Migration
- `migrate_csv_to_d1.py` - Migrates metadata only (not CSV data)

### Lambda
- `lambda_functions/processor.py`
  - `insert_metadata_to_d1()` - Inserts metadata with R2 paths
  - No longer inserts temperature points

### SvelteKit
- `src/lib/db.ts`
  - `queryTemperatureMetadata()` - Fetches metadata from D1, CSV from R2 (histogram/avg; no points in JSON)
  - `queryTemperaturePointsBuffer()` - Same CSV path; returns packed float32 triplets for map tiling
  - `parseCSV()` - Parses R2 CSV data
- `src/routes/api/feature/[...id]/temperature/[date]/+server.ts` - Temperature metadata JSON
- `src/routes/api/feature/[...id]/temperature/[date]/points/+server.ts` - Binary temperature points (`application/octet-stream`)
- `src/routes/api/feature/[...id]/temperature/+server.ts` - Latest date metadata JSON (no points)

## Benefits

1. **Cost Efficient**
   - D1: ~1,000 rows (free tier: 5M rows)
   - R2: ~10GB files (free tier: 10GB)

2. **Performance**
   - Metadata queries are instant (D1 indexes)
   - CSV files are already in optimal format
   - No need to reconstruct large datasets from DB

3. **Scalability**
   - Adding new features doesn't explode D1 usage
   - R2 scales to petabytes

4. **Maintainability**
   - CSV format is human-readable for debugging
   - Easy to re-process or migrate data
   - D1 schema remains simple

## Migration Steps

1. **Apply new schema** (drops temperature_data table):
   ```bash
   wrangler d1 migrations apply sat-water-temps-db
   ```

2. **Migrate metadata** (not CSV data):
   ```bash
   python migrate_csv_to_d1.py
   ```

3. **Deploy updated Lambda** (inserts metadata only)

4. **Deploy SvelteKit** (reads from R2)

## Future Considerations

### If we need faster queries
- Consider caching frequent queries in Cloudflare Workers KV
- Pre-aggregate data for common visualizations

### If CSVs become too large
- Use compression (gzip CSVs in R2)
- Consider columnar formats (Parquet) for analytics

### If we need real-time updates
- Keep recent data in D1 (last 7 days)
- Archive older data to R2
- Best of both worlds for hot/cold data

## Conclusion

This hybrid architecture leverages the strengths of each service:
- **D1**: Fast, queryable metadata
- **R2**: Unlimited, cheap file storage

It's the right tool for the right job! 🎯
