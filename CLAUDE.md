# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
npm install

# Development (frontend only, no D1/R2 bindings)
npm run dev                    # Runs at http://localhost:5173

# Development with Cloudflare bindings (D1 + R2)
npm run build && npm run wrangler:dev   # Runs at http://localhost:8788

# Type checking
npm run lint                   # tsc --noEmit on functions/

# Deploy frontend to Cloudflare Pages
npm run deploy

# Database migrations
npx wrangler d1 migrations apply sat-water-temps-db --remote
npx wrangler d1 migrations apply sat-water-temps-db --local

# Deploy Lambda functions (requires AWS credentials)
cd terraform && terraform apply
```

## Verifying Display Changes

When making frontend/UI changes, verify them using the Cursor browser extension (if available):

1. **Visit the development server** (assume it's already running):
   - Try http://localhost:5173 (frontend-only, `npm run dev`)
   - Or http://localhost:8788 (full stack with Cloudflare bindings, `npm run wrangler:dev`)

2. **Use Cursor browser extension**:
   - The cursor-browser-extension MCP server provides tools to navigate and interact with web pages
   - Navigate to the local development URL and verify visual changes, test interactions, and check responsive behavior
   - This is especially useful for testing UI components, styling changes, and user interactions without leaving the editor

3. **Alternative**: Open the development URL in your regular browser if the Cursor browser extension is not available

## Architecture Overview

This is a satellite water temperature monitoring platform with a split architecture:

### Frontend (Cloudflare)
- **SvelteKit** app deployed on Cloudflare Pages
- Uses **Cloudflare D1** (SQLite) for metadata queries
- Uses **Cloudflare R2** for storing temperature data (CSVs, TIFs, PNGs)
- API routes in `src/routes/api/` access D1/R2 via `platform.env.DB` and `platform.env.R2_DATA`

### Backend Processing (AWS)
- **Lambda functions** in `lambda_functions/` (Python, deployed as Docker images to ECR)
- **Step Functions** orchestrate polling of NASA AppEEARS API
- Daily CloudWatch trigger initiates processing pipeline
- Processed data uploaded to Cloudflare R2/D1 from Lambda

### Data Flow
1. CloudWatch → Initiator Lambda (submits AppEEARS task)
2. Step Function polls Status Checker Lambda until task completes
3. Manifest Processor Lambda sends SQS messages (one per scene)
4. Processor Lambda downloads ECOSTRESS data, processes rasters, uploads to R2/D1

## Key Files

- `src/lib/db.ts` - D1/R2 query functions, hybrid storage pattern (D1 metadata + R2 CSVs)
- `src/routes/api/` - SvelteKit API endpoints
- `lambda_functions/processor.py` - Main processing logic (raster filtering, PNG generation)
- `terraform/` - AWS infrastructure (Lambda, Step Functions, SQS, ECR)
- `wrangler.toml` - Cloudflare bindings (D1 database ID, R2 bucket)
- `migrations/` - D1 schema migrations

## Data Storage Pattern

Temperature data uses a hybrid approach:
- **D1 `temperature_metadata`** - Stores min/max temps, dates, CSV paths
- **R2** - Stores actual CSV files, TIFs, PNGs at paths like `ECO/{feature_id}/lake/{filename}`

The `csv_path` column in D1 points to the R2 object key.

## Feature IDs and AIDs

- Features are water bodies (lakes/reservoirs) identified by name (e.g., "Songkhla")
- AID (Area ID) is a 1-indexed number corresponding to polygon order in `static/polygons_new.geojson`
- Lambda functions use AID for processing; frontend uses feature names
