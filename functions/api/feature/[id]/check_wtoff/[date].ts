import { type Env } from '../../../_shared';

// Check if water is off for a specific date
export async function onRequest(context: { 
  env: Env; 
  params: { id: string; date: string } 
}): Promise<Response> {
  const { env, params } = context;
  
  try {
    const result = await env.DB.prepare(
      "SELECT wtoff FROM temperature_metadata WHERE feature_id = ? AND date = ?"
    ).bind(params.id, params.date).first();
    
    if (!result) {
      return new Response(JSON.stringify({ wtoff: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      });
    }
    
    return new Response(
      JSON.stringify({ wtoff: Boolean(result.wtoff) }),
      { status: 200, headers: { "content-type": "application/json" } }
    );
  } catch (err) {
    console.error('D1 query error:', err);
    return new Response(JSON.stringify({ wtoff: true }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
}

