// Hybrid architecture: D1 for metadata, R2 for temperature data

import type { D1Database, R2Bucket } from '@cloudflare/workers-types';
import Papa from 'papaparse';

type GeoPoint = { lng: number; lat: number; temperature: number };

/**
 * Parse CSV text into geographic coordinate array
 * CSV now contains longitude, latitude directly (no pixel coordinate conversion needed)
 */
function parseCSV(csvText: string): GeoPoint[] {
  const result = Papa.parse(csvText, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (header: string) => header.trim(),
    transform: (value: string) => value.trim()
  });

  if (result.errors.length > 0) {
    console.warn('CSV parsing errors:', result.errors);
  }

  return result.data.map((row: any) => ({
    lng: parseFloat(row.longitude || row.x || 0),
    lat: parseFloat(row.latitude || row.y || 0),
    temperature: parseFloat(row.LST_filter || row.temperature || 0)
  }));
}

/**
 * Build GeoJSON FeatureCollection from geo points
 */
function buildGeoJSON(points: GeoPoint[]) {
  return {
    type: 'FeatureCollection' as const,
    features: points.map(p => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
      properties: { temperature: p.temperature }
    }))
  };
}

/**
 * Compute histogram bins from temperature data
 */
function computeHistogram(temps: number[], numBins = 6): Array<{ range: string; count: number }> {
  if (!temps.length) return [];
  
  const min = Math.min(...temps);
  const max = Math.max(...temps);
  const binWidth = (max - min) / numBins;
  
  const bins = new Array(numBins).fill(0);
  for (const t of temps) {
    const idx = Math.min(Math.floor((t - min) / binWidth), numBins - 1);
    bins[idx]++;
  }
  
  return bins.map((count, i) => ({
    range: (min + i * binWidth).toFixed(1),
    count
  }));
}

/**
 * Query temperature data: metadata from D1, CSV data from R2
 * Returns GeoJSON ready for MapLibre (CSV contains lon/lat directly)
 */
export async function queryTemperatureData(
  db: D1Database,
  r2: R2Bucket | undefined,
  featureId: string,
  date: string
) {
  try {
    // Get metadata from D1
    const metaResult = await db
      .prepare(
        "SELECT min_temp, max_temp, wtoff, csv_path FROM temperature_metadata WHERE feature_id = ? AND date = ?"
      )
      .bind(featureId, date)
      .first();

    if (!metaResult) {
      return null;
    }

    if (!metaResult.csv_path) {
      console.error(`No CSV path in metadata for ${featureId} ${date}`);
      return null;
    }

    if (!r2) {
      console.error(`R2 bucket not available`);
      return null;
    }

    // Fetch CSV from R2 using the path stored in D1
    const csvPath = String(metaResult.csv_path);
    const csvObject = await r2.get(csvPath);
    
    if (!csvObject) {
      console.error(`CSV not found in R2: ${csvPath}`);
      return null;
    }

    const csvText = await csvObject.text();
    const geoPoints = parseCSV(csvText);
    const temps = geoPoints.map(p => p.temperature);
    
    return {
      geojson: buildGeoJSON(geoPoints),
      min_max: [metaResult.min_temp, metaResult.max_temp],
      histogram: computeHistogram(temps),
      avg: temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : 0,
      date: date,
      wtoff: Boolean(metaResult.wtoff),
    };
  } catch (err) {
    console.error("Error fetching temperature data:", err);
    return null;
  }
}

export async function getFeatureDates(db: D1Database, featureId: string) {
  try {
    const result = await db
      .prepare(
        "SELECT date FROM temperature_metadata WHERE feature_id = ? ORDER BY date DESC"
      )
      .bind(featureId)
      .all();

    return result.results?.map((r: any) => r.date) || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getLatestDate(db: D1Database, featureId: string): Promise<string | null> {
  try {
    const result = await db
      .prepare("SELECT latest_date FROM features WHERE id = ?")
      .bind(featureId)
      .first();

    const latest = result?.latest_date;
    return latest != null ? String(latest) : null;
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

export async function getProcessingJobs(
  db: D1Database,
  limit: number = 100,
  status?: string
) {
  try {
    let query = `
      SELECT id, job_type, task_id, feature_id, date, status,
             started_at, completed_at, duration_ms, error_message, metadata
      FROM processing_jobs
    `;

    if (status) {
      query += ` WHERE status = ?`;
    }

    query += ` ORDER BY started_at DESC LIMIT ?`;

    const stmt = db.prepare(query);
    const result = status
      ? await stmt.bind(status, limit).all()
      : await stmt.bind(limit).all();

    return result.results || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getEcostressRequests(
  db: D1Database,
  limit: number = 50,
  status?: string
) {
  try {
    let query = `
      SELECT
        er.id,
        er.task_id,
        er.trigger_type,
        er.triggered_by,
        er.description,
        er.start_date,
        er.end_date,
        er.scenes_count,
        er.created_at,
        er.updated_at,
        er.error_message,
        (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process') as total_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'success') as success_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'failed') as failed_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'started') as running_jobs,
        CASE
          WHEN er.task_id IS NULL THEN 'pending'
          WHEN (SELECT status FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'scrape' LIMIT 1) = 'failed' THEN 'failed'
          WHEN er.scenes_count IS NULL OR er.scenes_count = 0 THEN 'processing'
          WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status IN ('success', 'failed')) >= er.scenes_count THEN
            CASE
              WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'failed') > 0 THEN 'completed_with_errors'
              ELSE 'completed'
            END
          ELSE 'processing'
        END as status
      FROM ecostress_requests er
    `;

    if (status) {
      query += ` WHERE status = ?`;
    }

    query += ` ORDER BY er.created_at DESC LIMIT ?`;

    const stmt = db.prepare(query);
    const result = status
      ? await stmt.bind(status, limit).all()
      : await stmt.bind(limit).all();

    return result.results || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getEcostressRequestDetail(
  db: D1Database,
  id: number
) {
  try {
    const request = await db
      .prepare(`
        SELECT
          er.id,
          er.task_id,
          er.trigger_type,
          er.triggered_by,
          er.description,
          er.start_date,
          er.end_date,
          er.scenes_count,
          er.created_at,
          er.updated_at,
          er.error_message,
          CASE
            WHEN er.task_id IS NULL THEN 'pending'
            WHEN (SELECT status FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'scrape' LIMIT 1) = 'failed' THEN 'failed'
            WHEN er.scenes_count IS NULL OR er.scenes_count = 0 THEN 'processing'
            WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status IN ('success', 'failed')) >= er.scenes_count THEN
              CASE
                WHEN (SELECT COUNT(*) FROM processing_jobs pj WHERE pj.task_id = er.task_id AND pj.job_type = 'process' AND pj.status = 'failed') > 0 THEN 'completed_with_errors'
                ELSE 'completed'
              END
            ELSE 'processing'
          END as status
        FROM ecostress_requests er
        WHERE er.id = ?
      `)
      .bind(id)
      .first();

    if (!request) return null;

    const jobs = request.task_id
      ? await db
          .prepare(`
            SELECT id, job_type, task_id, feature_id, date, status,
                   started_at, completed_at, duration_ms, error_message, metadata
            FROM processing_jobs
            WHERE task_id = ?
              AND started_at >= ?
            ORDER BY started_at DESC
          `)
          .bind(request.task_id, request.created_at)
          .all()
      : { results: [] };

    return {
      request,
      jobs: jobs.results || []
    };
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

