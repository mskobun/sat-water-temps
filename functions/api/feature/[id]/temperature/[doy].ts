import { queryTemperatureData, type Env } from '../../../_shared';

// Get temperature data for a specific date from D1
export async function onRequest(context: { env: Env; params: { id: string; doy: string } }): Promise<Response> {
  const { env, params } = context;
  
  const result = await queryTemperatureData(env, params.id, params.doy);
  
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

