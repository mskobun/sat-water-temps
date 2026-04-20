# Daily Processing Overview

This document describes the current automated ingestion flow in the repo.

The old AppEEARS submit/poll/manifest pipeline has been removed. The current system uses direct discovery plus SQS fan-out:

- ECOSTRESS initiator queries CMR-STAC through `earthaccess`
- Landsat initiator queries the USGS STAC API
- both initiators send per-feature/per-date messages to SQS
- a single processor Lambda routes each message to the correct source-specific processor

## High-level flow

### ECOSTRESS

```text
CloudWatch schedule
  -> ECOSTRESS initiator Lambda
  -> CMR-STAC search via earthaccess
  -> SQS messages
  -> processor Lambda router
  -> ecostress.processor
  -> R2 + D1
```

### Landsat

```text
CloudWatch schedule
  -> Landsat initiator Lambda
  -> USGS STAC search
  -> SQS messages
  -> processor Lambda router
  -> landsat.processor
  -> R2 + D1
```

## AWS components

### Scheduled triggers

Defined in [terraform/scheduler.tf](/Users/rin/sw/pro/sat-water-temps/terraform/scheduler.tf).

- ECOSTRESS runs daily
- Landsat runs daily on its own schedule

Both schedules invoke their respective initiator Lambdas directly.

### SQS queue

Defined in [terraform/main.tf](/Users/rin/sw/pro/sat-water-temps/terraform/main.tf).

The queue decouples search/discovery from raster processing and allows parallel processing across features and dates.

### Initiator Lambdas

- [lambda_functions/ecostress/initiator.py](/Users/rin/sw/pro/sat-water-temps/lambda_functions/ecostress/initiator.py)
- [lambda_functions/landsat/initiator.py](/Users/rin/sw/pro/sat-water-temps/lambda_functions/landsat/initiator.py)

Each initiator:

- computes a default date window based on `data_delay_days`
- optionally filters to one feature
- searches the source catalog
- groups results by feature and date
- writes request/job state to D1
- sends SQS messages for downstream processing

### Processor Lambda router

[lambda_functions/processor.py](/Users/rin/sw/pro/sat-water-temps/lambda_functions/processor.py)

This is the single SQS-triggered Lambda entrypoint. It routes messages by payload:

- `source=ecostress` -> `ecostress.processor`
- `source=landsat` -> `landsat.processor`
- `type=backfill:*` -> `backfill.*`

The SQS event source mapping is defined in [terraform/lambdas.tf](/Users/rin/sw/pro/sat-water-temps/terraform/lambdas.tf).

## Data sources

### ECOSTRESS

The ECOSTRESS initiator uses `earthaccess.search_data()` against CMR-STAC for `ECO_L2T_LSTE` version `002`, then extracts the required band hrefs for processing.

### Landsat

The Landsat initiator queries the USGS STAC API at `https://landsatlook.usgs.gov/stac-server` for the `landsat-c2l2-st` collection, then extracts the required assets for temperature and QA processing.

## What processors produce

Source-specific processors generate derived outputs and metadata, then store them in Cloudflare:

- D1 rows in `temperature_metadata`
- D1 job/request logs
- R2 data assets such as CSV, Parquet, TIF, and PNG files

The worker app then serves those assets through the SvelteKit API routes.

## Manual triggering

The admin UI can trigger ingest runs through `/api/admin/trigger`, which records a request in D1 and invokes the relevant initiator Lambda URL using AWS IAM credentials configured in Cloudflare.

Relevant file:

- [src/routes/api/admin/trigger/+server.ts](/Users/rin/sw/pro/sat-water-temps/src/routes/api/admin/trigger/+server.ts)

## Local equivalent

For local development, `local_fill` bypasses SQS and runs the same processing path in-process for one feature and date range.

```bash
cd lambda_functions
uv run python -m local_fill --help
```

## Notes on removed architecture

The following are no longer part of the current runtime design:

- AppEEARS task submission and polling
- Step Functions orchestration
- manifest processor Lambda
- status checker Lambda

`terraform/step_function.tf` is left in the repo only as a note that Step Functions were removed.
