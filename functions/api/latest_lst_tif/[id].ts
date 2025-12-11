import { getObject, buildFeaturePath, type Env } from '../_shared';

export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const indexPath = buildFeaturePath(params.id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const pngKey = buildFeaturePath(params.id, `${latest}_filter_relative.png`);
  return getObject(env, pngKey, "image/png");
}

