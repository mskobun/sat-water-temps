// Shared utilities for Pages Functions

export interface Env {
  R2_DATA: R2Bucket;
  DB: D1Database;
}

export const BUCKET_PREFIX = "ECO";

export async function getObject(
  env: Env,
  key: string,
  contentType?: string
): Promise<Response> {
  const obj = await env.R2_DATA.get(key);
  if (!obj) return new Response(JSON.stringify({ error: "Not found" }), { status: 404 });
  const headers = new Headers();
  if (contentType) headers.set("content-type", contentType);
  headers.set("cache-control", "public, max-age=300");
  return new Response(obj.body, { headers });
}

export async function getJson<T = unknown>(env: Env, key: string): Promise<Response> {
  const obj = await env.R2_DATA.get(key);
  
  if (!obj) {
    return new Response(JSON.stringify({ error: "Not found", key }), { status: 404 });
  }
  
  const text = await obj.text();
  
  try {
    const data = JSON.parse(text) as T;
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "cache-control": "public, max-age=120",
      },
    });
  } catch (err) {
    console.error('JSON parse error:', err);
    return new Response("Invalid JSON", { status: 500 });
  }
}

export function buildFeaturePath(featureId: string, suffix: string): string {
  return `${BUCKET_PREFIX}/${featureId}/lake/${suffix}`;
}

// D1 query helpers
export async function queryTemperatureData(
  env: Env,
  featureId: string,
  date: string
): Promise<{ data: any[]; min_max: [number, number]; date: string; wtoff: boolean } | null> {
  try {
    // Get metadata
    const metaResult = await env.DB.prepare(
      "SELECT min_temp, max_temp, wtoff FROM temperature_metadata WHERE feature_id = ? AND date = ?"
    ).bind(featureId, date).first();
    
    if (!metaResult) {
      return null;
    }
    
    // Get temperature data
    const dataResult = await env.DB.prepare(
      "SELECT x, y, temperature FROM temperature_data WHERE feature_id = ? AND date = ? ORDER BY id"
    ).bind(featureId, date).all();
    
    return {
      data: dataResult.results || [],
      min_max: [metaResult.min_temp, metaResult.max_temp],
      date: date,
      wtoff: Boolean(metaResult.wtoff)
    };
  } catch (err) {
    console.error('D1 query error:', err);
    return null;
  }
}

export async function getFeatureDates(env: Env, featureId: string): Promise<string[]> {
  try {
    const result = await env.DB.prepare(
      "SELECT date FROM temperature_metadata WHERE feature_id = ? ORDER BY date DESC"
    ).bind(featureId).all();
    
    return result.results?.map((r: any) => r.date) || [];
  } catch (err) {
    console.error('D1 query error:', err);
    return [];
  }
}

export async function getLatestDate(env: Env, featureId: string): Promise<string | null> {
  try {
    const result = await env.DB.prepare(
      "SELECT latest_date FROM features WHERE id = ?"
    ).bind(featureId).first();
    
    return result?.latest_date || null;
  } catch (err) {
    console.error('D1 query error:', err);
    return null;
  }
}
