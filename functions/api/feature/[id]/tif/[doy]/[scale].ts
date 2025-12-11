import { getObject, buildFeaturePath, type Env } from '../../../../_shared';

export async function onRequest(context: { 
  env: Env; 
  params: { id: string; doy: string; scale: string } 
}): Promise<Response> {
  const { env, params } = context;
  const featureId = params.id;
  
  // Extract name and location from featureId (format: "name/location" or just "name")
  const [name, location = "lake"] = featureId.split("/");
  const pngKey = buildFeaturePath(featureId, `${name}_${location}_${params.doy}_filter_${params.scale}.png`);
  return getObject(env, pngKey, "image/png");
}

