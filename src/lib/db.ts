// Hybrid architecture: D1 for metadata, R2 for temperature data

import type { D1Database, R2Bucket } from '@cloudflare/workers-types';
import Papa from 'papaparse';

export const BUCKET_PREFIX = "ECO";

export function buildFeaturePath(featureId: string, suffix: string): string {
  return `${BUCKET_PREFIX}/${featureId}/lake/${suffix}`;
}

/**
 * Parse CSV text into temperature data array
 */
function parseCSV(csvText: string): Array<{ x: number; y: number; temperature: number }> {
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
    x: parseFloat(row.x || 0),
    y: parseFloat(row.y || 0),
    temperature: parseFloat(row.LST_filter || row.temperature || 0)
  }));
}

/**
 * Query temperature data: metadata from D1, CSV data from R2
 */
export async function queryTemperatureData(
  db: D1Database,
  r2: R2Bucket | undefined,
  featureId: string,
  date: string
) {
  try {
    // Get metadata and CSV path from D1
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
    const data = parseCSV(csvText);

    return {
      data,
      min_max: [metaResult.min_temp, metaResult.max_temp],
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

export async function getLatestDate(db: D1Database, featureId: string) {
  try {
    const result = await db
      .prepare("SELECT latest_date FROM features WHERE id = ?")
      .bind(featureId)
      .first();

    return result?.latest_date || null;
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

