# Satellite Water Temperature Monitoring

A web platform for monitoring water temperature data from ECOSTRESS satellites. Visualizes temperature trends across water bodies in Southeast Asia with interactive maps, charts, and historical data.

## Architecture

- **Frontend**: SvelteKit deployed on Cloudflare Pages
- **Backend Processing**: AWS Lambda functions orchestrated by Step Functions
- **Storage**: Cloudflare R2 (object storage) + D1 (database)
- **Data Source**: NASA AppEEARS API (ECOSTRESS LST data)

The system automatically processes daily satellite data:
1. CloudWatch triggers Initiator Lambda daily
2. Initiator submits task to AppEEARS API
3. Step Function polls for completion
4. Manifest Processor extracts file lists
5. Processor Lambda downloads, processes, and stores data in R2/D1

See [DAILY_PROCESSING_OVERVIEW.md](./DAILY_PROCESSING_OVERVIEW.md) for detailed pipeline documentation.

## Tech Stack

- **Frontend**: SvelteKit, TypeScript, Tailwind CSS, Leaflet
- **Backend**: AWS Lambda (Python), Step Functions, SQS
- **Storage**: Cloudflare D1 (SQLite), Cloudflare R2 (S3-compatible)
- **Infrastructure**: Terraform, Cloudflare Pages

## Local Development

### Prerequisites

- Node.js 20+
- npm
- Wrangler CLI (installed via npm)
- Cloudflare account with D1 and R2 access

### Setup

```bash
# Install dependencies
npm install

# Authenticate with Cloudflare
npx wrangler login

# Run dev server (frontend only, no bindings)
npm run dev

# Or run with full Cloudflare bindings (D1 + R2)
npm run build
npm run wrangler:dev
```

The app runs at:
- `http://localhost:5173` (Vite dev server, no bindings)
- `http://localhost:8788` (Wrangler dev, with bindings)

### Database Migrations

```bash
# Apply migrations to remote database
npx wrangler d1 migrations apply sat-water-temps-db --remote

# Apply migrations to local database
npx wrangler d1 migrations apply sat-water-temps-db --local
```

See [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) for detailed development guide.

## Deployment

### Frontend (Cloudflare Pages)

```bash
npm run deploy
```

Or connect your GitHub repo to Cloudflare Pages for automatic deployments.

### Backend (AWS Lambda)

Infrastructure is managed with Terraform:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Lambda functions are deployed as Docker images to ECR. See `terraform/` directory for infrastructure definitions.

## Configuration

### Wrangler (`wrangler.toml`)

- D1 database: `sat-water-temps-db`
- R2 bucket: `multitifs`
- Database ID: Update after Terraform creates D1 database

### Environment Variables

**Lambda Functions:**
- `APPEEARS_USER` / `APPEEARS_PASS`: NASA AppEEARS credentials
- `STATE_MACHINE_ARN`: Step Function ARN
- `SQS_QUEUE_URL`: SQS queue URL
- `R2_ENDPOINT`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`: Cloudflare R2
- `D1_DATABASE_ID`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`: Cloudflare D1

Set via Terraform or AWS Lambda environment variables.

## Project Structure

```
.
├── src/                    # SvelteKit frontend
│   ├── routes/            # Pages and API routes
│   └── lib/               # Shared utilities
├── lambda_functions/      # AWS Lambda handlers
│   ├── initiator.py       # Submits AppEEARS tasks
│   ├── status_checker.py  # Polls task status
│   ├── manifest_processor.py  # Processes file manifests
│   └── processor.py       # Downloads and processes data
├── terraform/             # Infrastructure as code
├── migrations/            # D1 database migrations
└── static/                # Static assets (GeoJSON polygons)
```

## API Endpoints

- `GET /api/polygons` - Get GeoJSON polygons for all features
- `GET /api/feature/[id]/get_dates` - Get available dates for a feature
- `GET /api/feature/[id]/temperature` - Get temperature data (metadata + CSV)
- `GET /api/feature/[id]/tif/[doy]/[scale]` - Get temperature visualization
- `GET /api/latest_lst_tif/[id]` - Get latest temperature image
- `GET /api/admin/jobs` - Admin job tracking dashboard

## Documentation

- [DAILY_PROCESSING_OVERVIEW.md](./DAILY_PROCESSING_OVERVIEW.md) - Data processing pipeline
- [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) - Development setup guide
- [D1_SCHEMA_DOCUMENTATION.sql](./D1_SCHEMA_DOCUMENTATION.sql) - Database schema
