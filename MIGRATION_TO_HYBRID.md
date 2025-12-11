# Migration to Hybrid Architecture - Summary

## What Changed

We switched from attempting to store all temperature data in D1 to a **hybrid D1 + R2 architecture**.

## Why?

**The Problem:**
- Features like "Bay" have 207,800+ temperature points per date
- Full migration would require **5+ million D1 rows**
- D1 free tier: **100,000 rows/day limit**
- Would take **50+ days** and immediately blow through quotas

**The Solution:**
- Keep temperature CSVs in R2 (where they already are)
- Use D1 only for metadata, file paths, and job tracking
- Reduces D1 usage to **~1,000 rows** (well within free tier)

## Files Changed

### 1. Database Schema
**File**: `migrations/0001_init_schema.sql`
- ❌ Removed `temperature_data` table
- ✅ Added R2 file paths to `temperature_metadata` (csv_path, tif_path, png_path)
- ✅ Added more metadata fields (mean_temp, median_temp, std_dev, etc.)
- **Result**: Schema is now metadata-only

### 2. Migration Script
**File**: `migrate_csv_to_d1.py`
- ❌ Removed `parse_csv_from_r2()` function
- ❌ Removed `insert_temperature_data()` function
- ✅ Added `count_csv_rows()` to get row count without parsing
- ✅ Updated `insert_metadata()` to include R2 file paths
- **Result**: Only migrates metadata (10-100x faster)

### 3. Lambda Processor
**File**: `lambda_functions/processor.py`
- ❌ Removed `insert_temperature_data_to_d1()` function
- ✅ Created `insert_metadata_to_d1()` function
- ✅ Inserts metadata with R2 file paths after CSV upload
- **Result**: Lambda only writes metadata to D1

### 4. SvelteKit Database Helpers
**File**: `src/lib/db.ts`
- ❌ Removed D1 query for temperature_data table
- ✅ Added `parseCSV()` function
- ✅ Updated `queryTemperatureData()` to:
  1. Fetch metadata from D1
  2. Fetch CSV from R2 using path
  3. Parse and return data
- **Result**: API transparently serves data from R2

### 5. SvelteKit API Routes
**Files**: 
- `src/routes/api/feature/[id]/temperature/+server.ts`
- `src/routes/api/feature/[id]/temperature/[doy]/+server.ts`
- ✅ Added R2 bucket access (`platform.env.R2_BUCKET`)
- ✅ Pass both DB and R2 to `queryTemperatureData()`
- **Result**: Routes now fetch from R2

### 6. Documentation
**Files**: 
- `HYBRID_ARCHITECTURE.md` (NEW) - Full explanation
- `D1_MIGRATION_GUIDE.md` (UPDATED) - Added hybrid notes
- `MIGRATION_TO_HYBRID.md` (NEW) - This file

## Benefits

### Cost
- **Before**: Would exceed D1 free tier immediately
- **After**: ~1,000 D1 rows (well within 5M free tier)

### Performance
- **Before**: Large queries reconstructing datasets
- **After**: Fast metadata queries + optimized CSV reads

### Scalability
- **Before**: Limited by D1 row quotas
- **After**: R2 scales to petabytes

## Next Steps

1. **Apply new schema**:
   ```bash
   wrangler d1 migrations apply sat-water-temps-db --remote
   ```

2. **Run migration** (metadata only, very fast now):
   ```bash
   python migrate_csv_to_d1.py
   ```

3. **Deploy Lambda** (processor.py updated)

4. **Deploy SvelteKit** (API routes updated)

## Migration Status

After running the updated migration script:
- ✅ Features table: ~49 rows
- ✅ Temperature metadata: ~500 rows (metadata + paths)
- ✅ Processing jobs: Empty initially, fills over time
- ✅ CSV files: Remain in R2 unchanged

**Total D1 rows**: ~550 (vs 5+ million if we stored everything)

## Architecture Diagram

```
┌─────────────────┐
│   Frontend      │
│   (SvelteKit)   │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────┐
│  SvelteKit API Route                │
│  /api/feature/[id]/temperature      │
│                                     │
│  1. Query D1 for metadata + paths  │
│  2. Fetch CSV from R2              │
│  3. Parse & return                 │
└────┬───────────────────────┬────────┘
     │                       │
     ↓                       ↓
┌──────────┐         ┌──────────────┐
│    D1    │         │      R2      │
│          │         │              │
│ features │         │  CSV files   │
│ metadata │         │  TIF files   │
│ jobs     │         │  PNG files   │
│          │         │              │
│ ~500 rows│         │  10GB+ data  │
└──────────┘         └──────────────┘
```

## Rollback Plan

If needed, the old CSV-only system still works:
- CSV files are unchanged in R2
- index.json files are still maintained
- Just revert the SvelteKit API routes

But this hybrid approach is objectively better! 🎯
