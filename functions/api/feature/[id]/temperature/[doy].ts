import { getJson, buildFeaturePath, type Env } from '../../../_shared';

export async function onRequest(context: { env: Env; params: { id: string; doy: string } }): Promise<Response> {
  const { env, params } = context;
  const metaKey = buildFeaturePath(params.id, `metadata/${params.doy}_filter_metadata.json`);
  return getJson(env, metaKey);
}

