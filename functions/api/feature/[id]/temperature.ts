import { getLatestDate, queryTemperatureData, type Env } from '../../_shared';

// Get latest temperature data with metadata from D1
export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const featureId = params.id;
  
  // Get latest date for this feature
  const latestDate = await getLatestDate(env, featureId);
  if (!latestDate) {
    return new Response(JSON.stringify({ error: "Feature not found" }), { status: 404 });
  }
  
  // Query temperature data from D1
  const result = await queryTemperatureData(env, featureId, latestDate);
  if (!result) {
    return new Response(JSON.stringify({ error: "Temperature data not found" }), { status: 404 });
  }
  
  return new Response(JSON.stringify(result), {
    status: 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=120"
    }
  });
}

