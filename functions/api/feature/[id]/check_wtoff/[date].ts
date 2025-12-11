import { buildFeaturePath, type Env } from '../../../_shared';

export async function onRequest(context: { 
  env: Env; 
  params: { id: string; date: string } 
}): Promise<Response> {
  const { env, params } = context;
  const metaKey = buildFeaturePath(params.id, `metadata/${params.date}_filter_metadata.json`);
  const metaObj = await env.R2_DATA.get(metaKey);
  
  if (!metaObj) {
    return new Response(JSON.stringify({ wtoff: true }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
  
  const meta = JSON.parse(await metaObj.text());
  return new Response(
    JSON.stringify({ wtoff: !!meta?.wtoff, files: meta?.files || [] }),
    { status: 200, headers: { "content-type": "application/json" } }
  );
}

