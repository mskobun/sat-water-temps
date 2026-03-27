// D1 for metadata, R2 for data files (Parquet, TIFs, PNGs)

import type { D1Database } from '@cloudflare/workers-types';

/** D1-only observation metadata (no CSV parsing). */
export type ObservationMeta = {
  date: string;
  wtoff: boolean;
  source: string;
  pixel_size: number | null;
  pixel_size_x: number | null;
  /** Raster CRS (e.g. EPSG:32651 for Landsat UTM). */
  source_crs: string | null;
  /** Affine transform coefficients a..f (rasterio order). */
  transform_a: number | null;
  transform_b: number | null;
  transform_c: number | null;
  transform_d: number | null;
  transform_e: number | null;
  transform_f: number | null;
};

export async function queryObservationMeta(
  db: D1Database,
  featureId: string,
  date: string
): Promise<ObservationMeta | null> {
  try {
    const row = await db
      .prepare(
        `SELECT wtoff, source, pixel_size, pixel_size_x,
         source_crs, transform_a, transform_b, transform_c, transform_d, transform_e, transform_f
         FROM temperature_metadata WHERE feature_id = ? AND date = ?`
      )
      .bind(featureId, date)
      .first();

    if (!row) return null;

    const ps = row.pixel_size;
    const pixel_size = ps != null && ps !== '' ? Number(ps) : null;
    const psx = row.pixel_size_x;
    const pixel_size_x = psx != null && psx !== '' ? Number(psx) : null;
    const num = (v: unknown) =>
      v != null && v !== '' && !Number.isNaN(Number(v)) ? Number(v) : null;

    return {
      date,
      wtoff: Boolean(row.wtoff),
      source: String(row.source || 'ecostress'),
      pixel_size,
      pixel_size_x,
      source_crs: row.source_crs != null && row.source_crs !== '' ? String(row.source_crs) : null,
      transform_a: num(row.transform_a),
      transform_b: num(row.transform_b),
      transform_c: num(row.transform_c),
      transform_d: num(row.transform_d),
      transform_e: num(row.transform_e),
      transform_f: num(row.transform_f)
    };
  } catch (err) {
    console.error('Error fetching observation meta:', err);
    return null;
  }
}

export async function getParquetPaths(db: D1Database, featureId: string): Promise<string[]> {
  const result = await db.prepare(
    'SELECT DISTINCT parquet_path FROM temperature_metadata WHERE feature_id = ? AND parquet_path IS NOT NULL'
  ).bind(featureId).all();
  return (result.results || []).map((r: any) => String(r.parquet_path));
}

export type ArchiveEntry = {
  date: string;
  source: string;
  data_points: number | null;
};

export type FeatureStatsHistoryEntry = {
  date: string;
  source: string;
  min_temp: number | null;
  max_temp: number | null;
  mean_temp: number | null;
  median_temp: number | null;
  std_dev: number | null;
  data_points: number | null;
  water_pixel_count: number | null;
  land_pixel_count: number | null;
  wtoff: boolean;
};

export async function getFeatureArchive(
  db: D1Database,
  featureId: string
): Promise<ArchiveEntry[]> {
  try {
    const result = await db
      .prepare(
        `SELECT date, source, data_points
         FROM temperature_metadata
         WHERE feature_id = ?
         ORDER BY date DESC`
      )
      .bind(featureId)
      .all();

    return (result.results || []).map((r: any) => ({
      date: r.date,
      source: String(r.source || 'ecostress'),
      data_points: r.data_points != null ? Number(r.data_points) : null,
    }));
  } catch (err) {
    console.error('D1 query error:', err);
    return [];
  }
}

export async function getFeatureStatsHistory(
  db: D1Database,
  featureId: string
): Promise<FeatureStatsHistoryEntry[]> {
  try {
    const result = await db
      .prepare(
        `SELECT
          date,
          source,
          min_temp,
          max_temp,
          mean_temp,
          median_temp,
          std_dev,
          data_points,
          water_pixel_count,
          land_pixel_count,
          wtoff
         FROM temperature_metadata
         WHERE feature_id = ?
         ORDER BY date DESC`
      )
      .bind(featureId)
      .all();

    const num = (v: unknown) =>
      v != null && v !== '' && !Number.isNaN(Number(v)) ? Number(v) : null;

    return (result.results || []).map((r: any) => ({
      date: String(r.date),
      source: String(r.source || 'ecostress'),
      min_temp: num(r.min_temp),
      max_temp: num(r.max_temp),
      mean_temp: num(r.mean_temp),
      median_temp: num(r.median_temp),
      std_dev: num(r.std_dev),
      data_points: num(r.data_points),
      water_pixel_count: num(r.water_pixel_count),
      land_pixel_count: num(r.land_pixel_count),
      wtoff: Boolean(r.wtoff)
    }));
  } catch (err) {
    console.error('D1 query error:', err);
    return [];
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

