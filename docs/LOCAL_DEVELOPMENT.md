# Local Development Guide

This guide covers the current local workflow for the Cloudflare app and the Lambda processing code.

## Stack

- SvelteKit on Cloudflare Pages
- Cloudflare D1 for feature metadata, requests, jobs, and settings
- Cloudflare R2 for CSV, Parquet, TIF, and PNG assets
- AWS Lambda for ECOSTRESS and Landsat ingestion

## Prerequisites

- Node.js 20+
- npm
- Python with `uv`
- Cloudflare access for D1 and R2
- NASA Earthdata credentials for processor runs

## Install

```bash
npm install
```

## Local app modes

### Frontend only

```bash
npm run dev
```

Runs Vite at `http://localhost:5173`.

Use this for UI work only. Cloudflare bindings are not available in this mode.

### Full stack with Cloudflare bindings

```bash
npm run wrangler:dev
```

Runs the built app at `http://localhost:8788` with:

- local D1
- remote R2

To run fully against remote Cloudflare resources:

```bash
npm run wrangler:dev:remote
```

## Local D1 setup

Local D1 is stored in `.wrangler/state/v3/d1/`.

Seed it from production:

```bash
npm run db:export
npm run db:seed
```

Apply migrations:

```bash
npm run db:migrate:local
npm run db:migrate:remote
```

## Local R2 setup

Seed the local/static assets needed by Wrangler development:

```bash
npm run r2:seed:local
```

## Recommended local setup

```bash
npm install
npm run db:export
npm run db:seed
npm run r2:seed:local
npm run wrangler:dev
```

## Important routes to test

- `/`
- `/feature/[id]`
- `/archive/[id]`
- `/admin/jobs`
- `/admin/requests`
- `/admin/features`
- `/admin/settings`

## Important API routes

- `/api/polygons`
- `/api/feature/{id}/get_dates`
- `/api/feature/{id}/stats`
- `/api/feature/{id}/archive`
- `/api/feature/{id}/temperature`
- `/api/feature/{id}/temperature/{date}`
- `/api/feature/{id}/parquet`
- `/api/feature/{id}/tif/{date}/{scale}`
- `/api/feature/{id}/tif/{date}/file`
- `/api/admin/requests`
- `/api/admin/jobs`
- `/api/admin/features`
- `/api/admin/settings`
- `/api/admin/trigger`

## Running processors locally

The repo includes `local_fill`, which runs the processor pipeline in-process for one feature and date range.

Show help:

```bash
cd lambda_functions
uv run python -m local_fill --help
```

Examples:

```bash
cd lambda_functions

# Cloud runtime: writes to configured cloud D1 + R2
uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15

# Local runtime: writes to local Wrangler D1 + R2
uv run python -m local_fill --runtime local --source ecostress --feature NamTheun2 --start-date 2026-03-15
uv run python -m local_fill --runtime local --source landsat --feature Magat --start-date 2024-12-27
```

Prerequisites:

- NASA Earthdata credentials in `~/.netrc` or env vars
- for cloud runtime, the required R2/D1 credentials in `lambda_functions/.env`

## Tests and checks

```bash
npm run lint
uv run pytest tests/ -v
```

## Auth

Admin routes use Auth.js with AWS Cognito.

Local auth setup:

```bash
./scripts/setup-dev-auth.sh
```

## Troubleshooting

### D1 not available

- Use `npm run wrangler:dev`, not `npm run dev`
- Seed local data with `npm run db:export && npm run db:seed`
- Make sure migrations have been applied

### R2 not available

- Use Wrangler dev, not plain Vite dev
- Check `wrangler.toml`
- Seed required local assets with `npm run r2:seed:local`

### Local DB looks empty

- Re-run `npm run db:seed`
- Or verify you are using the intended mode: local vs remote

### Build or typecheck failures

- Run `npm run lint`
- Then run `npm run build` for the full production build output

## Related docs

- [README.md](../README.md)
- [HYBRID_ARCHITECTURE.md](../HYBRID_ARCHITECTURE.md)
- [R2_GZIP_BEHAVIOR.md](./R2_GZIP_BEHAVIOR.md)
