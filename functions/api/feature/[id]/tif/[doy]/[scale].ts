import { getObject, buildFeaturePath, type Env } from '../../../../_shared';

export async function onRequest(context: { 
  env: Env; 
  params: { id: string; doy: string; scale: string } 
}): Promise<Response> {
  const { env, params } = context;
  const pngKey = buildFeaturePath(params.id, `${params.doy}_filter_${params.scale}.png`);
  return getObject(env, pngKey, "image/png");
}

