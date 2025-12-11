# D1 Migration Deployment Guide (Hybrid Architecture)

> **⚠️ Important**: This project uses a **hybrid D1 + R2 architecture**. D1 stores only metadata and job logs (~500 rows), while temperature CSV data remains in R2 (200k+ rows per file). See [HYBRID_ARCHITECTURE.md](./HYBRID_ARCHITECTURE.md) for the full rationale.

This guide walks through deploying the D1 database for metadata and job tracking.

## Phase 1: Deploy D1 for Metadata

### Step 1: Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This will create:
- D1 database `sat-water-temps-db`
- Updated Lambda functions with D1 credentials

### Step 2: Update Wrangler Configuration

After Terraform creates the database, update `wrangler.toml` with the database ID:

```bash
# Get the database ID from Terraform
cd terraform
export DB_ID=$(terraform output -raw d1_database_id)
cd ..

# Update wrangler.toml
sed -i '' "s/database_id = \"\"/database_id = \"$DB_ID\"/" wrangler.toml
```

Or manually:
```bash
cd terraform
terraform output d1_database_id
# Copy the ID and paste it into wrangler.toml
```

### Step 3: Apply Database Migrations

```bash
# Apply all migrations to D1
npx wrangler d1 migrations apply sat-water-temps-db --remote
```

This runs the initial migration (`0001_init_schema.sql`) which creates:
- `features` - Feature metadata and latest dates
- `temperature_data` - Temperature point data
- `temperature_metadata` - Min/max temps and data points per date
- `processing_jobs` - Job tracking (for Phase 2)

**View migration status:**
```bash
npx wrangler d1 migrations list sat-water-temps-db --remote
```

**Tip:** D1 tracks which migrations have been applied, so it's safe to run `apply` multiple times.

### Step 4: Migrate Existing Data

Set up environment variables in `.env`:

```bash
# R2 credentials (for reading CSVs)
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key

# D1 credentials (for writing to database)
D1_DATABASE_ID=<from terraform output>
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

Run migration script:

```bash
# Dry run first to see what will be migrated
python migrate_csv_to_d1.py --dry-run

# Migrate all features
python migrate_csv_to_d1.py

# Or migrate a single feature for testing
python migrate_csv_to_d1.py --feature <feature_id>
```

Expected output:
```
Found 15 features
Migrate 15 features? (y/n): y

============================================================
Migrating feature: bakun
============================================================
  Found 45 CSV files
  Processing 2024010112345...
    CSV: 32 temperature points
  ✓ Inserted 32 temperature points to D1
  ...
  ✓ Migrated 45 dates
```

### Step 5: Deploy Updated Lambda Functions

The Lambda processor now inserts data into D1 automatically.

Build and push new Docker image:

```bash
# Build and push (this happens automatically via GitHub Actions)
# Or manually:
cd lambda_functions
docker build -t eco-lambda .
# Push to ECR...
```

Update Lambda functions:

```bash
cd terraform
terraform apply
```

### Step 6: Deploy Updated Pages Functions

```bash
# Deploy via GitHub Actions (automatic on push to main)
# Or manually:
npx wrangler pages deploy public

# Or use npm script
npm run deploy
```

### Step 7: Test the Migration

Test API endpoints:

```bash
# Get dates for a feature (should query D1)
curl https://your-domain.com/api/feature/bakun/get_dates

# Get latest temperature data (should query D1)
curl https://your-domain.com/api/feature/bakun/temperature

# Get specific date (should query D1)
curl https://your-domain.com/api/feature/bakun/temperature/2024010112345
```

Verify data:

```bash
# Check D1 directly
npx wrangler d1 execute sat-water-temps-db --remote --command \
  "SELECT COUNT(*) as total_points FROM temperature_data"

npx wrangler d1 execute sat-water-temps-db --remote --command \
  "SELECT feature_id, COUNT(*) as dates FROM temperature_metadata GROUP BY feature_id"
```

## Phase 2: Implement Job Tracking (Later)

After Phase 1 is complete and tested, implement job tracking:

1. Lambda functions already have D1 access
2. Add structured logging calls to Lambda handlers
3. Create admin status page at `/api/admin/jobs`
4. Set up CloudWatch alarms (optional)

See the plan document for details on Phase 2.

## Rollback Plan

If issues occur, you can rollback:

### Option 1: Revert API Functions

```bash
git revert <commit-hash>
npx wrangler pages deploy public
```

The old API code will fall back to reading CSVs from R2 (which are still there).

### Option 2: Keep Both Systems Running

The migration keeps CSVs in R2 for backward compatibility. You can:
- Use D1 for new API endpoints
- Keep old endpoints using R2 CSVs
- Gradually migrate traffic

## Data Consistency

During migration:
- **New data**: Lambda processor writes to both D1 and R2 (CSVs)
- **Old data**: Remains in R2 until migration script runs
- **API**: Reads from D1 after deployment

This ensures no data loss during transition.

## Monitoring

Monitor the migration:

```bash
# Check D1 row counts
npx wrangler d1 execute sat-water-temps-db --remote --command \
  "SELECT 
     (SELECT COUNT(*) FROM features) as features,
     (SELECT COUNT(*) FROM temperature_data) as data_points,
     (SELECT COUNT(*) FROM temperature_metadata) as dates"

# Check Lambda logs
aws logs tail /aws/lambda/eco-water-temps-processor --follow

# Check API response times
curl -w "@curl-format.txt" -o /dev/null -s https://your-domain.com/api/feature/bakun/temperature
```

## Estimated Timeline

- **Step 1-3**: 10 minutes (infrastructure setup)
- **Step 4**: 30-60 minutes (depending on data volume)
- **Step 5-6**: 15 minutes (deployment)
- **Step 7**: 15 minutes (testing)

**Total**: ~1.5-2 hours

## Troubleshooting

### "D1 credentials not configured" in Lambda logs

- Verify environment variables are set in Lambda
- Check Terraform applied correctly: `terraform output d1_database_id`
- Redeploy Lambda: `terraform apply`

### Migration script fails with "401 Unauthorized"

- Check `CLOUDFLARE_API_TOKEN` has D1 edit permissions
- Verify `CLOUDFLARE_ACCOUNT_ID` is correct
- Token needs: Account > D1 > Edit

### API returns empty results

- Check D1 has data: `npx wrangler d1 execute ...`
- Verify `wrangler.toml` has correct `database_id`
- Check `feature_id` format matches (e.g., "bakun" vs "bakun/lake")

### Slow API responses

- Check D1 indexes are created: `schema.sql` includes indexes
- Monitor D1 query times in Cloudflare dashboard
- Consider adding more indexes if needed

