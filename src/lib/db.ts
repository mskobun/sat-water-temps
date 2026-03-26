// Hybrid architecture: D1 for metadata, R2 for temperature data

import type { D1Database, R2Bucket, R2ObjectBody } from '@cloudflare/workers-types';
import Papa from 'papaparse';

type GeoPoint = { lng: number; lat: number; temperature: number };

/** Read R2 object text. Decompresses gzip if R2 didn't do it transparently. */
async function r2Text(obj: R2ObjectBody): Promise<string> {
  const raw = await obj.arrayBuffer();
  const bytes = new Uint8Array(raw);
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const decompressed = new Response(
      new Response(raw).body!.pipeThrough(new DecompressionStream('gzip'))
    );
    return decompressed.text();
  }
  return new TextDecoder().decode(raw);
}

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
 * Compute histogram bins from temperature data
 */
function computeHistogram(temps: number[], numBins = 6): Array<{ range: string; count: number }> {
  if (!temps.length) return [];
  
  let min = Infinity;
  let max = -Infinity;
  for (const t of temps) {
    if (t < min) min = t;
    if (t > max) max = t;
  }
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

/** JSON payload for chart/sidebar (no point geometry). */
export type TemperatureMetadata = {
  min_max: [unknown, unknown];
  histogram: Array<{ range: string; count: number }>;
  avg: number;
  date: string;
  wtoff: boolean;
  source: string;
  pixel_size: number | null;
  pixel_size_x: number | null;
};

async function getObservationCsvText(
  db: D1Database,
  r2: R2Bucket,
  featureId: string,
  date: string
): Promise<{ csvText: string; metaResult: Record<string, unknown> } | null> {
  const metaResult = await db
    .prepare(
      'SELECT min_temp, max_temp, mean_temp, wtoff, csv_path, source, pixel_size, pixel_size_x FROM temperature_metadata WHERE feature_id = ? AND date = ?'
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

  const csvPath = String(metaResult.csv_path);
  const csvObject = await r2.get(csvPath);

  if (!csvObject) {
    console.error(`CSV not found in R2: ${csvPath}`);
    return null;
  }

  const csvText = await r2Text(csvObject);
  return { csvText, metaResult };
}

/**
 * Temperature sidebar + color scale metadata (D1 + one CSV parse for histogram/avg).
 */
export async function queryTemperatureMetadata(
  db: D1Database,
  r2: R2Bucket | undefined,
  featureId: string,
  date: string
): Promise<TemperatureMetadata | null> {
  try {
    if (!r2) {
      console.error(`R2 bucket not available`);
      return null;
    }

    const loaded = await getObservationCsvText(db, r2, featureId, date);
    if (!loaded) return null;

    const { csvText, metaResult } = loaded;
    const geoPoints = parseCSV(csvText);
    const temps = geoPoints.map((p) => p.temperature);

    const ps = metaResult.pixel_size;
    const pixel_size = ps != null && ps !== '' ? Number(ps) : null;
    const psx = metaResult.pixel_size_x;
    const pixel_size_x = psx != null && psx !== '' ? Number(psx) : null;

    const meanFromDb = metaResult.mean_temp;
    const avgFromDb =
      meanFromDb != null && meanFromDb !== '' && Number.isFinite(Number(meanFromDb))
        ? Number(meanFromDb)
        : null;

    return {
      min_max: [metaResult.min_temp, metaResult.max_temp],
      histogram: computeHistogram(temps),
      avg: avgFromDb ?? (temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : 0),
      date,
      wtoff: Boolean(metaResult.wtoff),
      source: String(metaResult.source || 'ecostress'),
      pixel_size,
      pixel_size_x
    };
  } catch (err) {
    console.error('Error fetching temperature metadata:', err);
    return null;
  }
}

/** Packed float32 triplets: lng, lat, temperature (Kelvin), little-endian. */
export async function queryTemperaturePointsBuffer(
  db: D1Database,
  r2: R2Bucket | undefined,
  featureId: string,
  date: string
): Promise<ArrayBuffer | null> {
  try {
    if (!r2) {
      console.error(`R2 bucket not available`);
      return null;
    }

    const loaded = await getObservationCsvText(db, r2, featureId, date);
    if (!loaded) return null;

    const geoPoints = parseCSV(loaded.csvText);
    if (!geoPoints.length) {
      return new ArrayBuffer(0);
    }

    const out = new Float32Array(geoPoints.length * 3);
    let o = 0;
    for (const p of geoPoints) {
      out[o++] = p.lng;
      out[o++] = p.lat;
      out[o++] = p.temperature;
    }
    return out.buffer;
  } catch (err) {
    console.error('Error fetching temperature points buffer:', err);
    return null;
  }
}

export async function getFeatureDates(db: D1Database, featureId: string) {
  try {
    const result = await db
      .prepare(
        "SELECT date, source FROM temperature_metadata WHERE feature_id = ? ORDER BY date DESC"
      )
      .bind(featureId)
      .all();

    return result.results?.map((r: any) => ({ date: r.date, source: String(r.source || 'ecostress') })) || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getLatestDate(db: D1Database, featureId: string): Promise<string | null> {
  try {
    const result = await db
      .prepare("SELECT date FROM temperature_metadata WHERE feature_id = ? ORDER BY date DESC LIMIT 1")
      .bind(featureId)
      .first();

    return result ? String(result.date) : null;
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

export async function countJobsByStatus(db: D1Database) {
  try {
    const result = await db
      .prepare(`
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
          SUM(CASE WHEN status = 'started' THEN 1 ELSE 0 END) as started
        FROM processing_jobs
      `)
      .first();
    return {
      total: Number(result?.total || 0),
      success: Number(result?.success || 0),
      failed: Number(result?.failed || 0),
      started: Number(result?.started || 0),
    };
  } catch (err) {
    console.error("D1 query error:", err);
    return { total: 0, success: 0, failed: 0, started: 0 };
  }
}

export async function countJobsByFilter(db: D1Database, status?: string) {
  try {
    let query = `SELECT COUNT(*) as total FROM processing_jobs`;
    if (status) query += ` WHERE status = ?`;
    const result = status
      ? await db.prepare(query).bind(status).first()
      : await db.prepare(query).first();
    return Number(result?.total || 0);
  } catch (err) {
    console.error("D1 query error:", err);
    return 0;
  }
}

/**
 * Parse filter_stats JSON. Old 3-bit histograms (no buckets >= 8) pass through
 * as-is — nodata wasn't tracked so there's no reliable way to infer it.
 */
function parseFilterStats(
  raw: unknown,
) {
  if (!raw) return null;
  return JSON.parse(raw as string);
}

export async function getProcessingJobs(
  db: D1Database,
  limit: number = 50,
  status?: string,
  offset: number = 0
) {
  try {
    let query = `
      SELECT
        j.id, j.job_type, j.task_id, j.feature_id, j.date, j.status,
        j.started_at, j.completed_at, j.duration_ms, j.error_message, j.metadata,
        tm.filter_stats
      FROM processing_jobs j
      LEFT JOIN temperature_metadata tm
        ON j.feature_id = tm.feature_id AND j.date = tm.date
    `;

    if (status) {
      query += ` WHERE j.status = ?`;
    }

    query += ` ORDER BY j.started_at DESC LIMIT ? OFFSET ?`;

    const stmt = db.prepare(query);
    const result = status
      ? await stmt.bind(status, limit, offset).all()
      : await stmt.bind(limit, offset).all();

    // Parse JSON metadata and filter_stats
    return (result.results || []).map((job: any) => ({
      ...job,
      metadata: job.metadata ? JSON.parse(job.metadata as string) : null,
      filter_stats: parseFilterStats(job.filter_stats)
    }));
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getJobWithFilterStats(
  db: D1Database,
  jobId: number
) {
  try {
    const job = await db
      .prepare(`
        SELECT
          j.id, j.job_type, j.task_id, j.feature_id, j.date, j.status,
          j.started_at, j.completed_at, j.duration_ms, j.error_message, j.metadata,
          tm.filter_stats
        FROM processing_jobs j
        LEFT JOIN temperature_metadata tm
          ON j.feature_id = tm.feature_id AND j.date = tm.date
        WHERE j.id = ?
      `)
      .bind(jobId)
      .first();

    if (!job) return null;

    // Parse JSON fields
    return {
      ...job,
      metadata: job.metadata ? JSON.parse(job.metadata as string) : null,
      filter_stats: parseFilterStats(job.filter_stats)
    };
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

export async function getFeatures(db: D1Database) {
  try {
    const result = await db
      .prepare(`
        SELECT
          f.id, f.name, f.location, f.latest_date, f.last_updated,
          COUNT(j.id) as total_jobs,
          SUM(CASE WHEN j.status = 'success' THEN 1 ELSE 0 END) as success_jobs,
          SUM(CASE WHEN j.status = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
          SUM(CASE WHEN j.status = 'started' THEN 1 ELSE 0 END) as running_jobs,
          (SELECT COUNT(*) FROM temperature_metadata tm WHERE tm.feature_id = f.id) as date_count
        FROM features f
        LEFT JOIN processing_jobs j ON j.feature_id = f.id
        GROUP BY f.id
        ORDER BY f.name
      `)
      .all();
    return result.results || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getFeatureDetail(db: D1Database, featureId: string) {
  try {
    const feature = await db
      .prepare(`
        SELECT
          f.id, f.name, f.location, f.latest_date, f.last_updated,
          COUNT(j.id) as total_jobs,
          SUM(CASE WHEN j.status = 'success' THEN 1 ELSE 0 END) as success_jobs,
          SUM(CASE WHEN j.status = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
          SUM(CASE WHEN j.status = 'started' THEN 1 ELSE 0 END) as running_jobs,
          (SELECT COUNT(*) FROM temperature_metadata tm WHERE tm.feature_id = f.id) as date_count,
          MAX(CASE WHEN j.status = 'success' THEN j.completed_at END) as last_success_at
        FROM features f
        LEFT JOIN processing_jobs j ON j.feature_id = f.id
        WHERE f.id = ?
        GROUP BY f.id
      `)
      .bind(featureId)
      .first();
    return feature || null;
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

export async function getJobsByFeature(
  db: D1Database,
  featureId: string,
  limit: number = 50,
  offset: number = 0,
  status?: string
) {
  try {
    let query = `
      SELECT
        j.id, j.job_type, j.task_id, j.feature_id, j.date, j.status,
        j.started_at, j.completed_at, j.duration_ms, j.error_message, j.metadata,
        tm.filter_stats
      FROM processing_jobs j
      LEFT JOIN temperature_metadata tm
        ON j.feature_id = tm.feature_id AND j.date = tm.date
      WHERE j.feature_id = ?
    `;

    if (status) {
      query += ` AND j.status = ?`;
    }

    query += ` ORDER BY j.started_at DESC LIMIT ? OFFSET ?`;

    const stmt = db.prepare(query);
    const result = status
      ? await stmt.bind(featureId, status, limit, offset).all()
      : await stmt.bind(featureId, limit, offset).all();

    return (result.results || []).map((job: any) => ({
      ...job,
      metadata: job.metadata ? JSON.parse(job.metadata as string) : null,
      filter_stats: parseFilterStats(job.filter_stats)
    }));
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function countJobsByFeature(db: D1Database, featureId: string, status?: string) {
  try {
    let query = `SELECT COUNT(*) as total FROM processing_jobs WHERE feature_id = ?`;
    if (status) query += ` AND status = ?`;
    const result = status
      ? await db.prepare(query).bind(featureId, status).first()
      : await db.prepare(query).bind(featureId).first();
    return Number(result?.total || 0);
  } catch (err) {
    console.error("D1 query error:", err);
    return 0;
  }
}

export async function getDataRequests(
  db: D1Database,
  source: 'ecostress' | 'landsat',
  limit: number = 50,
  status?: string
) {
  try {
    const jobType = source === 'ecostress' ? 'process' : 'landsat_process';
    let query = `
      SELECT
        dr.*,
        (SELECT COUNT(*) FROM processing_jobs pj
         WHERE pj.task_id = dr.task_id AND pj.job_type = '${jobType}'
         AND pj.started_at >= dr.created_at) as total_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj
         WHERE pj.task_id = dr.task_id AND pj.job_type = '${jobType}'
         AND pj.status = 'success' AND pj.started_at >= dr.created_at) as success_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj
         WHERE pj.task_id = dr.task_id AND pj.job_type = '${jobType}'
         AND pj.status = 'failed' AND pj.started_at >= dr.created_at) as failed_jobs,
        (SELECT COUNT(*) FROM processing_jobs pj
         WHERE pj.task_id = dr.task_id AND pj.job_type = '${jobType}'
         AND pj.status = 'started' AND pj.started_at >= dr.created_at) as running_jobs
      FROM data_requests_with_status dr
      WHERE dr.source = ?
    `;

    const params: any[] = [source];

    if (status) {
      query += ` AND dr.status = ?`;
      params.push(status);
    }

    query += ` ORDER BY dr.created_at DESC LIMIT ?`;
    params.push(limit);

    const stmt = db.prepare(query);
    const result = await stmt.bind(...params).all();

    return result.results || [];
  } catch (err) {
    console.error("D1 query error:", err);
    return [];
  }
}

export async function getDataRequestDetail(
  db: D1Database,
  id: number,
  source: string
) {
  try {
    const request = await db
      .prepare(`SELECT * FROM data_requests_with_status WHERE id = ? AND source = ?`)
      .bind(id, source)
      .first();

    if (!request) return null;

    let jobsResult: { results: any[] };

    if (source === 'ecostress' && request.task_id) {
      jobsResult = await db
        .prepare(`
          SELECT j.id, j.job_type, j.task_id, j.feature_id, j.date, j.status,
                 j.started_at, j.completed_at, j.duration_ms, j.error_message, j.metadata,
                 tm.filter_stats
          FROM processing_jobs j
          LEFT JOIN temperature_metadata tm
            ON j.feature_id = tm.feature_id AND j.date = tm.date
          WHERE j.task_id = ?
            AND j.started_at >= ?
          ORDER BY j.started_at DESC
        `)
        .bind(request.task_id, request.created_at)
        .all();
    } else if (source === 'landsat') {
      jobsResult = await db
        .prepare(`
          SELECT j.id, j.job_type, j.task_id, j.feature_id, j.date, j.status,
                 j.started_at, j.completed_at, j.duration_ms, j.error_message, j.metadata,
                 tm.filter_stats
          FROM processing_jobs j
          LEFT JOIN temperature_metadata tm
            ON j.feature_id = tm.feature_id AND j.date = tm.date
          WHERE j.job_type = 'landsat_process'
            AND j.date >= ? || 'T00:00:00'
            AND j.date <= ? || 'T23:59:59'
            AND j.started_at >= ?
          ORDER BY j.started_at DESC
        `)
        .bind(request.start_date, request.end_date, request.created_at)
        .all();
    } else {
      jobsResult = { results: [] };
    }

    return {
      request,
      jobs: (jobsResult.results || []).map((job: any) => ({
        ...job,
        metadata: job.metadata ? JSON.parse(job.metadata as string) : null,
        filter_stats: parseFilterStats(job.filter_stats)
      }))
    };
  } catch (err) {
    console.error("D1 query error:", err);
    return null;
  }
}

