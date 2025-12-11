import { Router, error, json } from 'itty-router';

export interface Env {
  R2_DATA: R2Bucket;
}

const BUCKET_PREFIX = "ECO";

// Helper functions
async function getObject(
  env: Env,
  key: string,
  contentType?: string
): Promise<Response> {
  const obj = await env.R2_DATA.get(key);
  if (!obj) return new Response("Not found", { status: 404 });
  const headers = new Headers();
  if (contentType) headers.set("content-type", contentType);
  headers.set("cache-control", "public, max-age=300");
  return new Response(obj.body, { headers });
}

async function getJson<T = unknown>(env: Env, key: string): Promise<Response> {
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

function buildFeaturePath(featureId: string, suffix: string): string {
  return `${BUCKET_PREFIX}/${featureId}/lake/${suffix}`;
}

// Create router with proper typing
const router = Router<Request, [Env]>();

// Get polygons GeoJSON
router.get('/polygons', async (req, env) => {
  return getObject(env, "static/polygons_new.geojson", "application/geo+json");
});

router.get('/api/polygons', async (req, env) => {
  return getObject(env, "static/polygons_new.geojson", "application/geo+json");
});

// Get available dates for a feature
router.get('/feature/:id/get_dates', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  return getJson(env, indexPath);
});

router.get('/api/feature/:id/get_dates', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  return getJson(env, indexPath);
});

// Get archive (same as get_dates)
router.get('/feature/:id/archive', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  return getJson(env, indexPath);
});

router.get('/api/feature/:id/archive', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  return getJson(env, indexPath);
});

// Get latest LST TIF as PNG
router.get('/latest_lst_tif/:id', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const pngKey = buildFeaturePath(id, `${latest}_filter_relative.png`);
  return getObject(env, pngKey, "image/png");
});

router.get('/api/latest_lst_tif/:id', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const pngKey = buildFeaturePath(id, `${latest}_filter_relative.png`);
  return getObject(env, pngKey, "image/png");
});

// Get TIF image for specific date and scale
router.get('/feature/:id/tif/:doy/:scale', async (req, env) => {
  const { id, doy, scale } = req.params;
  const pngKey = buildFeaturePath(id, `${doy}_filter_${scale}.png`);
  return getObject(env, pngKey, "image/png");
});

router.get('/api/feature/:id/tif/:doy/:scale', async (req, env) => {
  const { id, doy, scale } = req.params;
  const pngKey = buildFeaturePath(id, `${doy}_filter_${scale}.png`);
  return getObject(env, pngKey, "image/png");
});

// Get temperature metadata for specific date
router.get('/feature/:id/temperature/:doy', async (req, env) => {
  const { id, doy } = req.params;
  const metaKey = buildFeaturePath(id, `metadata/${doy}_filter_metadata.json`);
  return getJson(env, metaKey);
});

router.get('/api/feature/:id/temperature/:doy', async (req, env) => {
  const { id, doy } = req.params;
  const metaKey = buildFeaturePath(id, `metadata/${doy}_filter_metadata.json`);
  return getJson(env, metaKey);
});

// Get latest temperature metadata
router.get('/feature/:id/temperature', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const metaKey = buildFeaturePath(id, `metadata/${latest}_filter_metadata.json`);
  return getJson(env, metaKey);
});

router.get('/api/feature/:id/temperature', async (req, env) => {
  const { id } = req.params;
  const indexPath = buildFeaturePath(id, "index.json");
  const indexObj = await env.R2_DATA.get(indexPath);
  if (!indexObj) return new Response("Not found", { status: 404 });
  const index = JSON.parse(await indexObj.text());
  const latest = index?.latest_date;
  if (!latest) return new Response("Not found", { status: 404 });
  const metaKey = buildFeaturePath(id, `metadata/${latest}_filter_metadata.json`);
  return getJson(env, metaKey);
});

// Check water turn-off status
router.get('/feature/:id/check_wtoff/:date', async (req, env) => {
  const { id, date } = req.params;
  const metaKey = buildFeaturePath(id, `metadata/${date}_filter_metadata.json`);
  const metaObj = await env.R2_DATA.get(metaKey);
  if (!metaObj) {
    return new Response(JSON.stringify({ wtoff: true }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
  const meta = JSON.parse(await metaObj.text());
  return new Response(
    JSON.stringify({ wtoff: !!meta?.wtoff, files: meta?.files || [] }),
    { status: 200, headers: { "content-type": "application/json" } }
  );
});

router.get('/api/feature/:id/check_wtoff/:date', async (req, env) => {
  const { id, date } = req.params;
  const metaKey = buildFeaturePath(id, `metadata/${date}_filter_metadata.json`);
  const metaObj = await env.R2_DATA.get(metaKey);
  if (!metaObj) {
    return new Response(JSON.stringify({ wtoff: true }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
  const meta = JSON.parse(await metaObj.text());
  return new Response(
    JSON.stringify({ wtoff: !!meta?.wtoff, files: meta?.files || [] }),
    { status: 200, headers: { "content-type": "application/json" } }
  );
});

// Download TIF file
router.get('/download_tif/:id/:filename', async (req, env) => {
  const { id, filename } = req.params;
  const key = buildFeaturePath(id, filename);
  return getObject(env, key, "application/octet-stream");
});

router.get('/api/download_tif/:id/:filename', async (req, env) => {
  const { id, filename } = req.params;
  const key = buildFeaturePath(id, filename);
  return getObject(env, key, "application/octet-stream");
});

// Download CSV file
router.get('/download_csv/:id/:filename', async (req, env) => {
  const { id, filename } = req.params;
  const key = buildFeaturePath(id, filename);
  return getObject(env, key, "text/csv");
});

router.get('/api/download_csv/:id/:filename', async (req, env) => {
  const { id, filename } = req.params;
  const key = buildFeaturePath(id, filename);
  return getObject(env, key, "text/csv");
});

// 404 handler
router.all('*', () => error(404, 'Not found'));

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return router.fetch(request, env);
  }
};
