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

```bash
# Frontend (Cloudflare Pages)
npm run deploy

# Backend (AWS Lambda)
cd terraform && terraform apply
```

## Architecture

- **Frontend**: SvelteKit on Cloudflare Pages
- **Database**: Cloudflare D1 (metadata) + R2 (CSV/TIF/PNG files)
- **Backend**: AWS Lambda + Step Functions for ECOSTRESS data processing
