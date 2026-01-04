# Daily ECOSTRESS Data Processing Overview

This document describes how the automatic daily processing of ECOSTRESS satellite data works, from scheduled trigger to final data storage.

## Architecture Overview

The system uses AWS Lambda functions orchestrated by AWS Step Functions, triggered daily by CloudWatch Events. The pipeline processes ECOSTRESS LST (Land Surface Temperature) data from NASA's AppEEARS API, filters and processes it, then stores results in Cloudflare R2 (object storage) and D1 (database).

```
CloudWatch Event (Daily) 
    ↓
Initiator Lambda (Submits AppEEARS task)
    ↓
Step Function (Polling Machine)
    ↓
Status Checker Lambda (Checks task status)
    ↓ (when done)
Manifest Processor Lambda (Processes file manifest)
    ↓
SQS Queue (Message queue)
    ↓
Processor Lambda (Downloads & processes files)
    ↓
R2 Storage + D1 Database
```

## Components

### 1. Daily Trigger (CloudWatch Event)

**File:** `terraform/scheduler.tf`

- **Schedule:** Runs once per day (`rate(1 day)`)
- **Target:** Initiator Lambda function
- **Purpose:** Automatically triggers the processing pipeline each day

The CloudWatch Event Rule (`eco-water-temps-daily-trigger`) is configured to invoke the Initiator Lambda function automatically.

### 2. Initiator Lambda

**File:** `lambda_functions/initiator.py`

**Responsibilities:**
- Authenticates with NASA AppEEARS API
- Loads ROI (Region of Interest) polygons from `static/polygons_new.geojson`
- Calculates date range (defaults to yesterday's data, configurable)
- Submits a task request to AppEEARS for ECOSTRESS product `ECO_L2T_LSTE.002`
- Requests multiple layers: `LST`, `LST_err`, `QC`, `water`, `cloud`, `EmisWB`, `height`
- Logs job start to D1 database
- Starts the Step Function execution with the task ID
- Logs job completion status

**Key Details:**
- Default date range: 1 day (yesterday)
- Product: `ECO_L2T_LSTE.002` (ECOSTRESS Level 2T Land Surface Temperature)
- Output format: GeoTIFF, geographic projection
- Timeout: 5 minutes (300 seconds)

**Output:** Task ID passed to Step Function

### 3. Step Function (Polling Machine)

**File:** `terraform/step_function.tf`

**State Machine Flow:**

1. **WaitDynamic** - Waits a dynamic number of seconds (starts at 30 seconds)
2. **CheckStatus** - Invokes Status Checker Lambda to check AppEEARS task status
3. **IsDone?** - Choice state that routes based on status:
   - `done` → Proceeds to `ProcessManifest`
   - `error` → Fails the execution
   - Otherwise → Goes to `DoubleWait`
4. **DoubleWait** - Doubles the wait time and loops back to `WaitDynamic` (exponential backoff)
5. **ProcessManifest** - Invokes Manifest Processor Lambda when task is complete
6. **FailState** - Terminal failure state

**Features:**
- Exponential backoff: Wait time doubles each iteration (30s → 60s → 120s → ...)
- Retry logic: Status checks retry up to 3 times with 60s intervals on failures
- Handles long-running AppEEARS tasks that may take hours to complete

### 4. Status Checker Lambda

**File:** `lambda_functions/status_checker.py`

**Responsibilities:**
- Authenticates with AppEEARS API
- Checks the status of a submitted task by task ID
- Returns status: `done`, `error`, or `processing`

**Key Details:**
- Timeout: 60 seconds
- Simple polling function called repeatedly by Step Function
- Returns status that determines Step Function flow

### 5. Manifest Processor Lambda

**File:** `lambda_functions/manifest_processor.py`

**Responsibilities:**
- Authenticates with AppEEARS API
- Retrieves the file manifest/bundle for completed task
- Extracts metadata from filenames (AID number and date using regex)
- Groups files by scene (AID + date combination)
- Sends messages to SQS queue, one per scene

**What is a "Scene"?**

A **scene** represents one satellite observation of one geographic feature (lake/polygon) on one specific date/time. It's identified by:
- **AID (Area ID)**: A 4-digit number (e.g., `0001`, `0002`) that maps to a specific polygon/feature in the `polygons_new.geojson` file. The AID corresponds to the polygon's index in the GeoJSON file (AID 1 = first polygon, AID 2 = second polygon, etc.).
- **Date**: Extracted from filename using pattern `doy(\d{13})` (day of year + timestamp)

Each scene contains multiple files - one for each data layer requested:
- `LST_doy...` (Land Surface Temperature)
- `LST_err_doy...` (Temperature error)
- `QC_doy...` (Quality Control)
- `water_doy...` (Water mask)
- `cloud_doy...` (Cloud mask)
- `EmisWB_doy...` (Emissivity)
- `height_doy...` (Elevation)

Example: Scene `0001_20240115123456` = Feature #1 (first polygon) observed on January 15, 2024 at 12:34:56 UTC, with 7 files (one per layer).

**Key Details:**
- Timeout: 5 minutes (300 seconds)
- Uses HTTP session with retry logic for reliability
- Groups files by scene ID (`{aid}_{date}`)
- Each SQS message contains: `task_id`, `scene_id`, and `files` array

**Output:** Multiple SQS messages (one per scene)

### 6. SQS Queue

**File:** `terraform/main.tf`

**Configuration:**
- Name: `eco-water-temps-processing-queue`
- Visibility timeout: 900 seconds (15 minutes, matches Processor Lambda timeout)
- Message retention: 86400 seconds (1 day)
- Triggers Processor Lambda automatically when messages arrive

**Purpose:** Decouples manifest processing from file processing, allowing parallel processing of multiple scenes.

### 7. Processor Lambda

**File:** `lambda_functions/processor.py`

**Responsibilities:**
- Triggered by SQS messages (one message per scene)
- Authenticates with AppEEARS API
- Downloads all files for a scene from AppEEARS bundle
- Processes raster data:
  - Reads multiple layers (LST, LST_err, QC, water, cloud, EmisWB, height)
  - Applies quality filters (invalid QC values, cloud masking)
  - Applies water mask (or uses water-only pixels if no mask available - "wtoff" mode)
  - Calculates statistics (min, max, mean, median, std dev)
- Generates outputs:
  - **GeoTIFF**: Filtered multi-band raster (LST, LST_err, QC, EmisWB, height)
  - **CSV**: Pixel-level data for archive downloads
  - **PNG**: Visualization images (relative scale, fixed scale, grayscale)
  - **Metadata JSON**: Statistics and processing info
- Uploads all outputs to Cloudflare R2 storage
- Inserts metadata into D1 database
- Updates feature index files in R2
- Logs job status to D1 (started/success/failed with duration)

**Key Details:**
- Timeout: 15 minutes (900 seconds)
- Memory: 3008 MB (for raster processing performance)
- Processes one scene per invocation
- Handles multiple scenes in parallel (via SQS batch processing)
- Uses `/tmp` directory for temporary file storage
- Cleans up temporary files after processing

**Processing Logic:**
1. **Quality Filtering:** Removes pixels with invalid QC values (`{15, 2501, 3525, 65535}`)
2. **Cloud Masking:** Removes cloud-contaminated pixels
3. **Water Masking:** 
   - If water mask exists: filters to water pixels only
   - If no water mask: uses all pixels and marks as "wtoff" (water turn-off)
4. **Statistics:** Calculates temperature statistics on filtered data
5. **Visualization:** Generates PNG images with different color scales for web display

**Storage Paths:**
- R2: `ECO/{name}/{location}/{base_name}.{ext}`
- D1: Metadata in `temperature_metadata` table, linked to `features` table

## Data Flow Example

1. **Day 1, 00:00 UTC:** CloudWatch Event triggers Initiator Lambda
2. **Initiator:** Submits AppEEARS task for yesterday's data (e.g., 2024-01-15)
3. **Step Function:** Starts polling every 30 seconds (then 60s, 120s, etc.)
4. **Status Checker:** Repeatedly checks task status
5. **After 2 hours:** AppEEARS task completes, status returns "done"
6. **Manifest Processor:** Retrieves manifest, finds 5 scenes, sends 5 SQS messages
7. **SQS:** Triggers Processor Lambda 5 times (one per scene)
8. **Processor (parallel):** Each instance downloads, processes, and uploads one scene
9. **Storage:** All data stored in R2, metadata in D1
10. **Complete:** Users can access data via web interface

## Error Handling

- **Initiator failures:** Logged to D1, task submission retried on next day
- **Step Function failures:** Retries status checks up to 3 times
- **Manifest Processor failures:** Step Function fails, can be manually retried
- **Processor failures:** SQS message returns to queue after visibility timeout, retried automatically
- **D1 logging:** All jobs logged with status, duration, and error messages for monitoring

## Monitoring

All processing jobs are logged to the D1 `processing_jobs` table with:
- Job type (`scrape`, `process`)
- Task ID
- Feature ID and date (for processing jobs)
- Status (`started`, `success`, `failed`)
- Duration (milliseconds)
- Error messages (if failed)
- Metadata JSON

This allows tracking of:
- Daily processing success rates
- Processing times
- Failed jobs for manual retry
- Historical processing patterns

## Configuration

Key environment variables:
- `APPEEARS_USER` / `APPEEARS_PASS`: NASA AppEEARS credentials
- `STATE_MACHINE_ARN`: Step Function ARN (set automatically by Terraform)
- `SQS_QUEUE_URL`: SQS queue URL (set automatically by Terraform)
- `R2_ENDPOINT`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`: Cloudflare R2 storage
- `D1_DATABASE_ID`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`: Cloudflare D1 database

## Infrastructure

All infrastructure is defined in Terraform:
- **scheduler.tf:** CloudWatch Event trigger
- **lambdas.tf:** Lambda function definitions (Initiator, Status Checker, Processor)
- **manifest_lambda.tf:** Manifest Processor Lambda
- **step_function.tf:** Step Function state machine
- **main.tf:** SQS queue and IAM roles/policies

Lambda functions are deployed as Docker images stored in AWS ECR, allowing for complex dependencies (rasterio, geopandas, etc.).

