// Shared utilities for Pages Functions

export interface Env {
  R2_DATA: R2Bucket;
}

export const BUCKET_PREFIX = "ECO";

export async function getObject(
  env: Env,
  key: string,
  contentType?: string
): Promise<Response> {
  const obj = await env.R2_DATA.get(key);
  console.log(await env.R2_DATA.list());
  if (!obj) return new Response(JSON.stringify({ error: "Not found" }), { status: 404 });
  const headers = new Headers();
  if (contentType) headers.set("content-type", contentType);
  headers.set("cache-control", "public, max-age=300");
  return new Response(obj.body, { headers });
}

export async function getJson<T = unknown>(env: Env, key: string): Promise<Response> {
  const obj = await env.R2_DATA.get(key);
  if (!obj) return new Response("Not found", { status: 404 });
  const text = await obj.text();
  try {
    const data = JSON.parse(text) as T;
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "content-type": "application/json",
        "cache-control": "public, max-age=120",
      },
    });
  } catch {
    return new Response("Invalid JSON", { status: 500 });
  }
}

export function buildFeaturePath(featureId: string, suffix: string): string {
  return `${BUCKET_PREFIX}/${featureId}/lake/${suffix}`;
}
