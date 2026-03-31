#!/usr/bin/env bash
# One-off script to backfill synthetic task_ids for existing ECOSTRESS data.
#
# 1. Assigns task_id = 'eco-{id}' to all ecostress data_requests missing one
# 2. Links processing_jobs to their data_request by date range + created_at
# 3. Fixes old MM-DD-YYYY dates to YYYY-MM-DD in data_requests
# 4. Fixes orphaned ecostress_submit jobs stuck at 'started'
#
# Usage: bash scripts/backfill-task-ids.sh
# Requires: npx wrangler (authenticated)

set -euo pipefail
DB="sat-water-temps-db"

run_sql() {
  npx wrangler d1 execute "$DB" --remote --command "$1" 2>&1
}

echo "=== Step 1: Fix MM-DD-YYYY dates to YYYY-MM-DD ==="
run_sql "
UPDATE data_requests
SET start_date = SUBSTR(start_date,7,4) || '-' || SUBSTR(start_date,1,2) || '-' || SUBSTR(start_date,4,2)
WHERE source = 'ecostress'
  AND start_date LIKE '__-__-____'
"
run_sql "
UPDATE data_requests
SET end_date = SUBSTR(end_date,7,4) || '-' || SUBSTR(end_date,1,2) || '-' || SUBSTR(end_date,4,2)
WHERE source = 'ecostress'
  AND end_date LIKE '__-__-____'
"
echo "Done."

echo ""
echo "=== Step 2: Assign synthetic task_ids to data_requests ==="
run_sql "
UPDATE data_requests
SET task_id = 'eco-' || CAST(id AS TEXT)
WHERE source = 'ecostress'
  AND task_id IS NULL
"
echo "Done."

echo ""
echo "=== Step 3: Link processing_jobs to data_requests by date range ==="
# For each request that has scenes, update matching ecostress_process jobs.
# Jobs match when their date falls in the request's date range and they started after the request.
run_sql "
UPDATE processing_jobs
SET task_id = (
  SELECT 'eco-' || CAST(dr.id AS TEXT)
  FROM data_requests dr
  WHERE dr.source = 'ecostress'
    AND processing_jobs.job_type = 'ecostress_process'
    AND processing_jobs.date >= dr.start_date || 'T00:00:00'
    AND processing_jobs.date <= dr.end_date || 'T23:59:59'
    AND processing_jobs.started_at >= dr.created_at
  ORDER BY dr.created_at DESC
  LIMIT 1
)
WHERE job_type = 'ecostress_process'
  AND task_id IS NULL
"
echo "Done."

echo ""
echo "=== Step 4: Link ecostress_submit jobs ==="
run_sql "
UPDATE processing_jobs
SET task_id = (
  SELECT 'eco-' || CAST(dr.id AS TEXT)
  FROM data_requests dr
  WHERE dr.source = 'ecostress'
    AND processing_jobs.started_at >= dr.created_at
  ORDER BY dr.created_at DESC
  LIMIT 1
)
WHERE job_type = 'ecostress_submit'
  AND task_id IS NULL
"
echo "Done."

echo ""
echo "=== Step 5: Mark orphaned 'started' submit jobs as failed ==="
run_sql "
UPDATE processing_jobs
SET status = 'failed',
    completed_at = started_at,
    error_message = 'Initiator crashed (earthaccess auth failure)'
WHERE job_type = 'ecostress_submit'
  AND status = 'started'
  AND started_at < $(date -v-1d +%s000)
"
echo "Done."

echo ""
echo "=== Verification ==="
echo "Requests still missing task_id:"
run_sql "SELECT COUNT(*) as cnt FROM data_requests WHERE source = 'ecostress' AND task_id IS NULL" | grep '"cnt"'

echo "Jobs still missing task_id:"
run_sql "SELECT COUNT(*) as cnt FROM processing_jobs WHERE job_type LIKE 'ecostress%' AND task_id IS NULL" | grep '"cnt"'

echo "Requests still with MM-DD-YYYY dates:"
run_sql "SELECT COUNT(*) as cnt FROM data_requests WHERE source = 'ecostress' AND start_date LIKE '__-__-____'" | grep '"cnt"'

echo ""
echo "=== Done ==="
