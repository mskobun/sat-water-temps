import { getObject, buildFeaturePath, type Env } from '../../_shared';

export async function onRequest(context: { 
  env: Env; 
  params: { id: string; filename: string } 
}): Promise<Response> {
  const { env, params } = context;
  const key = buildFeaturePath(params.id, params.filename);
  return getObject(env, key, "application/octet-stream");
}

