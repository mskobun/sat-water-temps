# Satellite Water Temperatures

Satellite water temperature monitoring platform for reservoir and lake observations from ECOSTRESS and Landsat.

The system has two main parts:

- SvelteKit app deployed to Cloudflare Pages
- Cloudflare D1 for metadata, requests, jobs, features, and settings
- Cloudflare R2 for polygons, GeoTIFFs, PNG previews, metadata JSON, and Parquet data
- Python Lambda ingestion pipelines for ECOSTRESS and Landsat
- Terraform-managed AWS infrastructure for Lambda, ECR, SQS, EventBridge Scheduler, and Cognito

## Repository Layout

- `src/` - SvelteKit UI, admin pages, and API routes
- `lambda_functions/` - ECOSTRESS/Landsat initiators, processors, shared helpers, and local CLIs
- `migrations/` - Cloudflare D1 schema migrations
- `terraform/` - AWS and Cloudflare infrastructure
- `scripts/` - local setup and data maintenance helpers
- `.github/workflows/deploy.yml` - CI/CD for tests, Lambda image deployment, Terraform, D1 migrations, and Pages
- `pyproject.toml` / `uv.lock` - Python dependencies managed by `uv`
- `package.json` / `package-lock.json` - Node dependencies managed by npm

## Prerequisites

- Node.js 20+
- npm
- `uv` for Python dependency and environment management
- Terraform, for infrastructure operations and local auth setup
- Cloudflare account access for Pages, D1, and R2
- AWS account access for Lambda, ECR, SQS, Scheduler, and Cognito
- NASA Earthdata credentials for processor runs

Install `uv` on macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

Windows and alternative install methods are documented by Astral: <https://docs.astral.sh/uv/getting-started/installation/>.

## Install

Install frontend dependencies:

```bash
npm install
```

Install/sync Python dependencies from `pyproject.toml` and `uv.lock`:

```bash
uv sync
```

The project targets Python `3.12` via `.python-version`. `uv run ...` will also create and sync the virtual environment automatically when needed.

## Local App Development

Frontend-only Vite development server:

```bash
npm run dev
```

Runs at `http://localhost:5173`. Use this for UI work that does not need Cloudflare bindings.

Full SvelteKit/Cloudflare worker runtime:

```bash
npm run wrangler:dev
```

Runs at `http://localhost:8788` with local D1 and the R2 binding from `wrangler.toml`.

Remote Cloudflare resources:

```bash
npm run wrangler:dev:remote
```

Runs locally but talks to remote D1/R2. Use carefully because it can affect production data.

## Local Data Setup

Local D1 is stored under `.wrangler/state/v3/d1/`.

```bash
npm run db:export              # Export remote D1 to seed.sql
npm run db:seed                # Reset local D1 and apply seed.sql
npm run db:migrate:local       # Apply migrations to local D1
npm run db:migrate:remote      # Apply migrations to remote D1
npm run r2:seed:local          # Upload static assets to local R2
```

Typical fresh local setup:

```bash
npm install
uv sync
npm run db:export
npm run db:seed
npm run r2:seed:local
npm run wrangler:dev
```

`static/` contains local polygon and favicon assets used by `npm run r2:seed:local` and local processor runs.

## Configuration

The SvelteKit app reads Cloudflare bindings and runtime variables from Wrangler. For local admin authentication, generate the required Cognito and Lambda invocation values from Terraform outputs:

```bash
./scripts/setup-dev-auth.sh
```

Python processor and maintenance scripts that write to cloud resources use these environment variables:

```bash
EARTHDATA_USERNAME=...
EARTHDATA_PASSWORD=...
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...
D1_DATABASE_ID=...
R2_ENDPOINT=...
R2_BUCKET_NAME=multitifs
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

NASA Earthdata credentials may also be provided through `~/.netrc`.

## Running Processors Locally

`local_fill` runs one source, feature, and date range in-process without SQS.

Show help:

```bash
cd lambda_functions
uv run python -m local_fill --help
```

Write to configured cloud D1/R2:

```bash
cd lambda_functions
uv run python -m local_fill --source ecostress --feature NamTheun2 --start-date 2026-03-15
```

Write to local Wrangler D1/R2:

```bash
cd lambda_functions
uv run python -m local_fill --runtime local --source ecostress --feature NamTheun2 --start-date 2026-03-15
uv run python -m local_fill --runtime local --source landsat --feature Magat --start-date 2024-12-27
```

With `--runtime local`, the CLI finds the repo root by walking up from the current directory for `wrangler.toml` and `static/`. Override with `--project-dir /path/to/repo` or `WRANGLER_PROJECT_DIR`.

## Tests And Checks

```bash
npm run lint                   # Svelte + TypeScript checks
npm run build                  # Production SvelteKit build
uv run pytest tests/ -v        # Lambda and shared Python tests
```

Regenerate Lambda `requirements.txt` from the locked Python project when dependencies change:

```bash
uv export --no-dev --format requirements-txt --output-file requirements.txt
```

## Main App Areas

- Public map and feature pages for browsing latest observations and historical archives
- Public dashboard for cross-feature processing status
- Protected admin area for submitting ingestion requests, reviewing jobs, managing features, and changing processing settings
- API routes under `src/routes/api/` for D1 metadata, R2 assets, admin actions, and Lambda trigger calls

## Authentication

Admin routes use Auth.js with AWS Cognito.

- Route protection: `src/hooks.server.ts`
- Auth configuration: `src/auth.ts`
- Local auth setup: `./scripts/setup-dev-auth.sh`
- Cognito infrastructure: `terraform/cognito.tf`

## Deployment

Deployment is automated through GitHub Actions on pushes to `main`.

The workflow:

- detects whether Lambda/backend or frontend files changed
- runs `uv run pytest tests/ -v` for Lambda/backend changes
- builds and pushes the Lambda Docker image to ECR
- runs `terraform apply -auto-approve` for infrastructure and Lambda updates
- runs `npm ci` and `npm run build` for frontend changes
- applies remote D1 migrations
- deploys `.svelte-kit/cloudflare` to Cloudflare Pages

Manual local deployment commands exist in `package.json` and Terraform, but normal deployment should happen through GitHub Actions.

GitHub Actions setup instructions are documented in `.github/workflows/README.md`.

## GitHub Actions

Workflow file: `.github/workflows/deploy.yml`.

Triggers:

- `push` to `main` when application, Lambda, migration, Terraform, or workflow files change
- manual `workflow_dispatch`, with `force_lambda_deploy` available

The workflow uses:

- `astral-sh/setup-uv` for Python tests and `requirements.txt` export
- `actions/setup-node` with Node 20 and npm cache
- AWS credentials from repository secrets
- Cloudflare credentials from repository secrets
- Terraform S3 backend configured in `terraform/backend.tf`
