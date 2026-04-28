# scripts/

Utility scripts for local development, data maintenance, and operations.

## Active / regularly used

### `r2-seed-local.sh`
Seeds the local Wrangler R2 emulator with static assets (feature polygons, favicon). Run once after a fresh checkout before using `npm run wrangler:dev`.

```bash
npm run r2:seed:local
# or directly:
bash scripts/r2-seed-local.sh
```

### `setup-dev-auth.sh`
Configures local Cognito credentials for admin route authentication during development. Run once per dev environment.

```bash
bash scripts/setup-dev-auth.sh
```

### `backfill_prod_monthly.py`
Invokes the production ECOSTRESS and Landsat initiator Lambdas month-by-month for historical backfills. Useful when onboarding new features or recovering from pipeline gaps.

```bash
cd scripts
uv run python backfill_prod_monthly.py --help
```

## Data generation

### `generate_parquet.py`
Regenerates per-feature Parquet files in R2 from existing D1 metadata and R2 CSVs. Run if Parquet files are missing or need to be rebuilt after a schema change.

```bash
cd scripts
uv run python generate_parquet.py --help
```

### `generate_pmtiles.py`
Generates PMTiles vector tiles from the feature polygon GeoJSON. Run if the polygon tile layer needs to be rebuilt.

```bash
cd scripts
uv run python generate_pmtiles.py --help
```

## Test fixtures

### `fetch_landsat_fixture.py`
Downloads a Landsat scene and saves it as a local fixture file for pytest. Run when test fixtures are missing or need refreshing.

```bash
cd scripts
uv run python fetch_landsat_fixture.py --help
```
