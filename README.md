# Satellite Water Temperatures

Satellite water temperature monitoring platform using ECOSTRESS data.

## Quick Start

```bash
npm install

# First-time setup: seed local database from prod
npm run db:export
npm run db:seed

# Start development server (local D1 + remote R2)
npm run wrangler:dev    # http://localhost:8788
```

## Development

### Local Database Staging

Local development uses a local D1 database with remote R2 for file access. This allows testing schema changes without affecting production.

| Command | Description |
|---------|-------------|
| `npm run dev` | Frontend only (no D1/R2) at :5173 |
| `npm run wrangler:dev` | Local D1 + remote R2 at :8788 |
| `npm run wrangler:dev:remote` | Full prod (remote D1 + R2) at :8788 |

### Database Commands

| Command | Description |
|---------|-------------|
| `npm run db:export` | Export prod D1 → `seed.sql` |
| `npm run db:seed` | Apply migrations + seed to local D1 |
| `npm run db:migrate:local` | Apply migrations locally |
| `npm run db:migrate:remote` | Apply migrations to prod |

### Schema Change Workflow

1. Create migration file in `migrations/`
2. `npm run db:migrate:local` — test locally
3. `npm run wrangler:dev` — verify with frontend
4. `npm run db:migrate:remote` — deploy to prod

### Refresh Local Data

```bash
npm run db:export && npm run db:seed
```

## Deployment

Deployment is automated via GitHub Actions on push to `main`.

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS credentials for Lambda/ECR |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token (D1, R2, Pages) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `R2_BUCKET_NAME` | R2 bucket name |
| `R2_ACCESS_KEY_ID` | R2 credentials for Lambda |
| `R2_SECRET_ACCESS_KEY` | R2 credentials |
| `R2_ENDPOINT` | R2 S3-compatible endpoint |
| `APPEEARS_USER` | NASA AppEEARS credentials |
| `APPEEARS_PASS` | NASA AppEEARS credentials |
| `PAGES_DOMAIN` | Production domain (e.g., `sat-water-temps.pages.dev`) |

### Manual Deployment

```bash
# Frontend (Cloudflare Pages)
npm run deploy

# Backend + Infrastructure (AWS Lambda, Cognito, etc.)
cd terraform && terraform apply
```

### Post-Deployment: Create Admin User

After first deploy, create an admin user for the `/admin` dashboard:

1. Go to AWS Console → Cognito → User Pools
2. Select `eco-water-temps-admin-pool`
3. Users → Create User
4. Enter email and temporary password

## Admin Authentication

Admin routes (`/admin/*`) are protected by AWS Cognito via Auth.js.

### Local Development with Auth

After deploying, run the setup script to create `.dev.vars`:

```bash
./scripts/setup-dev-auth.sh
```

This fetches Cognito credentials from Terraform and creates the `.dev.vars` file automatically.

## Architecture

- **Frontend**: SvelteKit on Cloudflare Pages
- **Database**: Cloudflare D1 (metadata) + R2 (CSV/TIF/PNG files)
- **Backend**: AWS Lambda + Step Functions for ECOSTRESS data processing
- **Auth**: AWS Cognito (ap-southeast-1) via Auth.js
