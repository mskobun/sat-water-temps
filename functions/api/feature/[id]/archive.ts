import { getJson, buildFeaturePath, type Env } from '../../_shared';

export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const indexPath = buildFeaturePath(params.id, "index.json");
  return getJson(env, indexPath);
}

