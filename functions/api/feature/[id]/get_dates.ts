import { getFeatureDates, type Env } from '../../_shared';

// Get all dates for a feature from D1
export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const dates = await getFeatureDates(env, params.id);
  
  return new Response(JSON.stringify(dates), {
    status: 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=120"
    }
  });
}

