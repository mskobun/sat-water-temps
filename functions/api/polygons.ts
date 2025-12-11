import { getObject, type Env } from './_shared';

export async function onRequest(context: { env: Env }): Promise<Response> {
  return getObject(context.env, "static/polygons_new.geojson", "application/geo+json");
}

