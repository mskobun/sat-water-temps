# Satellite Water Temperatures

Satellite water temperature monitoring platform with:

- a SvelteKit app on Cloudflare Pages
- D1 for metadata and job/request state
- R2 for rasters and derived data files
- Python Lambda pipelines for ECOSTRESS and Landsat ingestion

## What is in the repo

- `src/` — SvelteKit map UI, admin UI, and API routes
- `lambda_functions/` — ECOSTRESS/Landsat initiators, processors, shared helpers, and local CLIs
- `migrations/` — D1 schema migrations
- `terraform/` — AWS infrastructure for Lambda, ECR, scheduler, SQS, and Cognito
- `scripts/` — utility scripts for local seeding and data maintenance

## Current architecture

The Cloudflare side serves the user-facing app and admin dashboard. It reads feature metadata from D1 and data assets from R2.

The AWS side runs the ingestion pipeline. Manual or scheduled requests create `data_requests` rows, initiators fan work out, processors pull remote raster inputs, compute stats and outputs, then write metadata to D1 and files to R2.

Supported sources in the current codebase:

- `ecostress`
- `landsat`

## Main app surfaces

- `/` — map view
- `/feature/[id]` — per-feature detail page
- `/archive/[id]` — feature archive page
- `/admin/*` — protected admin pages for requests, jobs, features, and settings

## Main API routes

- `/api/polygons`
- `/api/feature/[id]/get_dates`
- `/api/feature/[id]/stats`
- `/api/feature/[id]/archive`
- `/api/feature/[id]/temperature`
- `/api/feature/[id]/temperature/[date]`
- `/api/feature/[id]/parquet`
- `/api/feature/[id]/tif/[date]/[scale]`
- `/api/feature/[id]/tif/[date]/file`
- `/api/admin/requests`
- `/api/admin/jobs`
- `/api/admin/features`
- `/api/admin/settings`
- `/api/admin/trigger`

## Development commands

```bash
npm install
npm run dev                    # Frontend only at http://localhost:5173
npm run wrangler:dev           # Full stack with local D1 + remote R2 at http://localhost:8788
npm run wrangler:dev:remote    # Full stack against remote D1 + remote R2 at http://localhost:8788
npm run lint                   # Svelte + TypeScript checks
uv run pytest tests/ -v        # Lambda unit tests
```

## Local data and migrations

Local D1 lives in `.wrangler/state/v3/d1/`.

```bash
npm run db:export              # Export remote D1 to seed.sql
npm run db:seed                # Reset local D1 and apply seed.sql
npm run db:migrate:local       # Apply migrations locally
npm run db:migrate:remote      # Apply migrations remotely
npm run r2:seed:local          # Seed local R2 with static assets
```

Typical local setup:

```bash
npm install
npm run db:export
npm run db:seed
npm run r2:seed:local
npm run wrangler:dev
```

## Running processors locally

`local_fill` runs the ingestion pipeline in-process for a single feature and date range without SQS.

Prerequisites:

- NASA Earthdata credentials in `~/.netrc` or env vars
- for cloud runtime, the required R2/D1 credentials in `lambda_functions/.env`

Examples:

```bash
cd lambda_functions

# Write to cloud resources
uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15

# Write to local Wrangler D1 + R2
uv run python -m local_fill --runtime local --source ecostress --feature NamTheun2 --start-date 2026-03-15
uv run python -m local_fill --runtime local --source landsat --feature Magat --start-date 2024-12-27
```

Help:

```bash
cd lambda_functions
uv run python -m local_fill --help
```

## Authentication

Admin routes use Auth.js with AWS Cognito.

- Route protection lives in `src/hooks.server.ts`
- Auth configuration lives in `src/auth.ts`
- Local setup helper: `./scripts/setup-dev-auth.sh`

## Deploy

```bash
npm run deploy
cd terraform && terraform apply
```

`npm run deploy` publishes the Cloudflare Pages app. Terraform manages the AWS Lambda infrastructure and Cognito resources.

## Key files

- `src/lib/db.ts` — D1 query helpers used by API routes
- `src/routes/api/` — SvelteKit server routes
- `lambda_functions/ecostress/` — ECOSTRESS initiator and processor
- `lambda_functions/landsat/` — Landsat initiator and processor
- `lambda_functions/common/` — shared storage, raster, metadata, and parquet helpers
- `lambda_functions/local_fill/` — local CLI entrypoint
- `wrangler.toml` — Cloudflare bindings and Pages config

## More context

- [CLAUDE.md](./CLAUDE.md) — contributor/agent notes
- [docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md) — detailed local workflow
- [HYBRID_ARCHITECTURE.md](./HYBRID_ARCHITECTURE.md) — D1/R2 storage design notes
