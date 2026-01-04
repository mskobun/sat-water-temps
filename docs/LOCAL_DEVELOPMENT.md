# Local Development Guide

This guide explains how to develop and test the SvelteKit application locally with Cloudflare D1 and R2.

## Prerequisites

- Node.js 20+
- npm or pnpm
- Wrangler CLI (installed via npm dependencies)
- Cloudflare account with:
  - D1 database access (`sat-water-temps-db`)
  - R2 bucket access (`multitifs`)

## Architecture

This project uses **SvelteKit with Cloudflare adapter**:
- **Frontend**: SvelteKit pages in `src/routes/`
- **API Routes**: SvelteKit API routes in `src/routes/api/`
- **Database**: D1 (metadata and job tracking)
- **Storage**: R2 (CSV, TIF, PNG files)
- **Hybrid Architecture**: D1 for small metadata, R2 for large data files

## Local Development

### 1. Install dependencies

```bash
npm install
```

### 2. Authenticate with Cloudflare

```bash
npx wrangler login
```

### 3. Set up local D1 database (optional)

For local development, you can use a local D1 database:

```bash
# Create local D1 database
npx wrangler d1 create sat-water-temps-db --local

# Apply migrations to local database
npx wrangler d1 migrations apply sat-water-temps-db --local
```

**Note**: The local database starts empty. You can either:
- Use the remote database (recommended for testing with real data)
- Run the migration script to populate local D1: `python migrate_csv_to_d1.py`

### 4. Run SvelteKit dev server

#### Option A: Using Vite dev server (fastest, no bindings)

```bash
npm run dev
```

This runs the standard SvelteKit dev server at `http://localhost:5173`. 
**Note**: D1 and R2 bindings won't work in this mode. Use for frontend-only development.

#### Option B: Using Wrangler Pages dev (with bindings)

```bash
# First build SvelteKit
npm run build

# Then run with Wrangler (includes D1 + R2 bindings)
npm run wrangler:dev
# or
npx wrangler pages dev .svelte-kit/cloudflare \
  --d1=DB=sat-water-temps-db \
  --r2=R2_DATA=multitifs \
  --compatibility-date=2025-12-11
```

This runs at `http://localhost:8788` with full Cloudflare bindings.

**For local D1 database**, add `--local`:
```bash
npx wrangler pages dev .svelte-kit/cloudflare \
  --d1=DB=sat-water-temps-db \
  --r2=R2_DATA=multitifs \
  --local \
  --compatibility-date=2025-12-11
```

### 5. Test the application

Once running:
- Visit `http://localhost:8788` (or `http://localhost:5173` for Vite) for the main page
- API endpoints are available at `/api/*`:
  - `http://localhost:8788/api/polygons` - Get GeoJSON polygons
  - `http://localhost:8788/api/feature/{id}/get_dates` - Get available dates from D1
  - `http://localhost:8788/api/feature/{id}/temperature` - Get temperature data (D1 metadata + R2 CSV)
  - `http://localhost:8788/api/latest_lst_tif/{id}` - Get latest temperature image from R2
  - `http://localhost:8788/admin/jobs` - Admin dashboard for job tracking

## Project Structure

```
.
├── src/
│   ├── routes/
│   │   ├── +page.svelte              # Landing page
│   │   ├── feature/[id]/+page.svelte # Feature detail page
│   │   ├── archive/[id]/+page.svelte # Archive page
│   │   ├── admin/jobs/+page.svelte   # Admin dashboard
│   │   └── api/                       # API routes
│   │       ├── feature/[id]/
│   │       │   ├── temperature/+server.ts
│   │       │   ├── get_dates/+server.ts
│   │       │   └── archive/+server.ts
│   │       └── latest_lst_tif/[id]/+server.ts
│   ├── lib/
│   │   └── db.ts                      # D1 query helpers
│   └── app.d.ts                       # TypeScript types for platform
├── migrations/                        # D1 migrations
│   ├── 0001_init_schema.sql
│   └── 0002_hybrid_architecture.sql
├── wrangler.toml                      # Cloudflare configuration
├── svelte.config.js                   # SvelteKit config
└── package.json                       # Dependencies
```

## Configuration

### Wrangler Configuration (`wrangler.toml`)

```toml
name = "sat-water-temps"
pages_build_output_dir = ".svelte-kit/cloudflare"
compatibility_date = "2025-12-11"

[[r2_buckets]]
binding = "R2_DATA"
bucket_name = "multitifs"

[[d1_databases]]
binding = "DB"
database_name = "sat-water-temps-db"
database_id = "6fbaa491-9631-4afa-9c8f-0e7b4c133fd5"
```

### Environment Variables

For local development, you can create a `.dev.vars` file (not committed):

```bash
# .dev.vars (optional, for custom config)
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

## Development Workflow

### Frontend Development (No Bindings Needed)

```bash
npm run dev
```

Use this for:
- UI/UX changes
- Component development
- Styling
- TypeScript type checking

### Full Stack Development (With Bindings)

```bash
npm run build
npm run wrangler:dev
```

Use this for:
- Testing API routes
- Testing D1 queries
- Testing R2 file access
- End-to-end feature testing

### Database Migrations

Apply migrations to remote database:
```bash
npx wrangler d1 migrations apply sat-water-temps-db --remote
```

Apply migrations to local database:
```bash
npx wrangler d1 migrations apply sat-water-temps-db --local
```

### Query Local D1 Database

```bash
# Interactive shell
npx wrangler d1 execute sat-water-temps-db --local

# Run SQL file
npx wrangler d1 execute sat-water-temps-db --local --file=query.sql

# Remote database
npx wrangler d1 execute sat-water-temps-db --remote --command="SELECT * FROM features LIMIT 5"
```

## Troubleshooting

### "Database not available" errors
- Make sure you're running with `wrangler pages dev` (not `vite dev`)
- Check that D1 binding is correct: `--d1=DB=sat-water-temps-db`
- Verify database exists: `npx wrangler d1 list`

### "R2 storage not available" errors
- Ensure R2 binding is passed: `--r2=R2_DATA=multitifs`
- Check bucket name matches `wrangler.toml`
- Verify you have R2 access in Cloudflare dashboard

### TypeScript errors in `platform.env`
- Make sure `src/app.d.ts` has correct types
- Check that `@cloudflare/workers-types` is installed
- Restart TypeScript server in your IDE

### SvelteKit build errors
- Run `npm run build` to see full error messages
- Check `svelte.config.js` uses `@sveltejs/adapter-cloudflare`
- Verify `vite.config.ts` is configured correctly

### Local D1 database is empty
- Run migrations: `npx wrangler d1 migrations apply sat-water-temps-db --local`
- Or use remote database: remove `--local` flag
- Or populate with migration script: `python migrate_csv_to_d1.py`

### Port already in use
- Change port: `npx wrangler pages dev .svelte-kit/cloudflare --port=8789`
- Or kill existing process: `lsof -ti:8788 | xargs kill`

## Quick Reference

```bash
# Install dependencies
npm install

# Dev with Vite (no bindings)
npm run dev

# Build SvelteKit
npm run build

# Dev with Wrangler (with bindings)
npm run wrangler:dev

# Apply D1 migrations (remote)
npx wrangler d1 migrations apply sat-water-temps-db --remote

# Apply D1 migrations (local)
npx wrangler d1 migrations apply sat-water-temps-db --local

# Query D1 database
npx wrangler d1 execute sat-water-temps-db --remote --command="SELECT * FROM features"

# Deploy to Cloudflare Pages
npm run deploy
```

## Hybrid Architecture Notes

This project uses a **hybrid architecture**:
- **D1**: Stores metadata (~500 rows) and job logs (~50 rows/day)
- **R2**: Stores large CSV files (200k+ rows each), TIFs, PNGs

When developing API routes:
- Query metadata from D1: `platform.env.DB`
- Fetch CSV files from R2: `platform.env.R2_DATA`
- See `src/lib/db.ts` for helper functions

For more details, see [HYBRID_ARCHITECTURE.md](./HYBRID_ARCHITECTURE.md).
