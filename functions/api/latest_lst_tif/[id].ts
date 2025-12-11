import { getObject, buildFeaturePath, getLatestDate, type Env } from '../_shared';

// Get latest temperature PNG image
export async function onRequest(context: { env: Env; params: { id: string } }): Promise<Response> {
  const { env, params } = context;
  const featureId = params.id;
  
  // Get latest date from D1
  const latestDate = await getLatestDate(env, featureId);
  if (!latestDate) {
    return new Response("Not found", { status: 404 });
  }
  
  // Extract name and location from featureId (format: "name/location" or just "name")
  const [name, location = "lake"] = featureId.split("/");
  const pngKey = buildFeaturePath(featureId, `${name}_${location}_${latestDate}_filter_relative.png`);
  return getObject(env, pngKey, "image/png");
}

