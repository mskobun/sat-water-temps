# CLAUDE.md

## Build and Development Commands

```bash
npm install
npm run dev                    # Frontend only at http://localhost:5173
npm run wrangler:dev           # Full stack (local D1 + remote R2) at http://localhost:8788
npm run wrangler:dev:remote    # Full stack (prod D1 + prod R2) at http://localhost:8788
npm run lint                   # tsc --noEmit on functions/
uv run pytest tests/ -v        # Run Lambda unit tests
cd lambda_functions && uv run python -m local_fill --help   # In-process fill: one feature + date range; add --runtime local for Wrangler D1+R2 (repo root found from cwd)
npm run deploy                 # Deploy frontend to Cloudflare Pages
cd terraform && terraform apply  # Deploy Lambda functions (requires AWS creds)
```

## Local Database

Local D1 stored in `.wrangler/state/v3/d1/`. Remote R2 used for file access.

```bash
npm run db:export              # Export prod D1 → seed.sql
npm run db:seed                # Reset local D1 + apply seed.sql
npm run db:migrate:local       # Test migrations locally
npm run db:migrate:remote      # Deploy migrations to prod
```

## Running Processors Locally (`local_fill`)

`local_fill` runs ECOSTRESS or Landsat processor pipelines in-process (no SQS) for a single feature and date range. Uses NASA Earthdata HTTPS (not S3) to open COGs, so no Earthdata S3 credentials are needed.

**Prerequisites:**
- NASA Earthdata credentials in `~/.netrc` (or `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` env vars)
- R2 creds in `.env` for `--runtime cloud`, or local Wrangler D1/R2 for `--runtime local`

```bash
# Cloud runtime — writes to prod D1 + R2 (needs .env with R2/D1 creds)
cd lambda_functions
uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15

# Local runtime — writes to Wrangler local D1 + R2 (no cloud creds needed)
cd lambda_functions
uv run python -m local_fill --runtime local --source ecostress --feature NamTheun2 --start-date 2026-03-15
uv run python -m local_fill --runtime local --source landsat  --feature Magat       --start-date 2024-12-27

# Seed local R2 with static assets (polygons, favicon) before first local run
npm run r2:seed:local
```

With `--runtime local`, repo root is found automatically by walking up from cwd for `wrangler.toml` + `static/`. Override with `--project-dir /path/to/repo` or `WRANGLER_PROJECT_DIR`.

ECOSTRESS uses HTTPS COG links by default when `--runtime local` (avoids local S3 auth issues). To force S3 links (Lambda behaviour): `--prefer-s3-hrefs`.

## UI Components

Uses **shadcn-svelte** (`src/lib/components/ui/`). Add new components: `npx shadcn-svelte@latest add <component>`. Docs: https://www.shadcn-svelte.com/docs/components

## Architecture Overview

Satellite water temperature monitoring platform.

**Frontend (Cloudflare):** SvelteKit on Cloudflare Pages, D1 (SQLite) for metadata, R2 for data files (CSVs, TIFs, PNGs). API routes access bindings via `platform.env.DB` and `platform.env.R2_DATA`.

**Backend (AWS):** Python Lambda functions in `lambda_functions/` (Docker → ECR). Scheduled task_poller Lambda orchestrates NASA AppEEARS API polling. Processor Lambda downloads ECOSTRESS data, processes rasters, uploads to R2/D1.

## Key Files

- `src/lib/db.ts` — D1/R2 query functions (D1 metadata + R2 CSVs)
- `src/routes/api/` — SvelteKit API endpoints
- `lambda_functions/ecostress/` — ECOSTRESS initiator + processor
- `lambda_functions/landsat/` — Landsat initiator + processor
- `lambda_functions/common/` — Shared helpers (storage, raster I/O, parquet, metadata)
- `lambda_functions/local_fill/` — Local processor CLI (`python -m local_fill`)
- `terraform/` — AWS infrastructure (Lambda, SQS, ECR)
- `wrangler.toml` — Cloudflare bindings
- `migrations/` — D1 schema migrations

## Data Storage

- **D1 `temperature_metadata`** — min/max temps, dates, csv_path (points to R2 key)
- **R2** — CSVs, TIFs, PNGs at `ECO/{feature_id}/lake/{filename}`

## Feature IDs and AIDs

- Features = water bodies identified by name (e.g., "Songkhla")
- AID = 1-indexed polygon order in `static/polygons_new.geojson`
- Lambda uses AID; frontend uses feature names

## Authentication

Admin routes (`/admin/*`) protected by Auth.js (@auth/sveltekit) + AWS Cognito. Route protection in `src/hooks.server.ts`. Config in `src/auth.ts`. Setup local auth: `./scripts/setup-dev-auth.sh`.
