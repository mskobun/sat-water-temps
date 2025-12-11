import { type Env } from '../../_shared';

// Get archive data (all dates with metadata) from D1
export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  
  try {
    // Query all dates with metadata for this feature
    const result = await env.DB.prepare(`
      SELECT date, min_temp, max_temp, data_points, wtoff
      FROM temperature_metadata
      WHERE feature_id = ?
      ORDER BY date DESC
    `).bind(params.id).all();
    
    const dates = result.results?.map((r: any) => r.date) || [];
    const latestDate = dates.length > 0 ? dates[0] : null;
    
    return new Response(JSON.stringify({
      dates,
      latest_date: latestDate,
      last_updated: new Date().toISOString()
    }), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "cache-control": "public, max-age=120"
      }
    });
  } catch (err) {
    console.error('D1 query error:', err);
    return new Response(JSON.stringify({ error: "Database error" }), { status: 500 });
  }
}

