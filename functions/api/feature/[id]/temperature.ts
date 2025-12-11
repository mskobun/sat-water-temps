import { getJson, buildFeaturePath, type Env } from '../../_shared';

// Get latest temperature metadata
export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const indexPath = buildFeaturePath(params.id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const metaKey = buildFeaturePath(params.id, `metadata/${latest}_filter_metadata.json`);
  return getJson(env, metaKey);
}

