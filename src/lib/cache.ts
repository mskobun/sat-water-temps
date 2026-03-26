/** Binary cache — uses CF Cache API in production, in-memory Map for local dev. */

const TTL = 300; // 5 minutes, in seconds
const memCache = new Map<string, { buf: ArrayBuffer; ts: number }>();

export async function getCache(key: string): Promise<ArrayBuffer | null> {
  if (typeof caches !== 'undefined') {
    const cache = await caches.open('parquet');
    const resp = await cache.match(new Request(`https://parquet-cache/${key}`));
    return resp ? resp.arrayBuffer() : null;
  }
  const entry = memCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > TTL * 1000) {
    memCache.delete(key);
    return null;
  }
  return entry.buf;
}

export async function setCache(key: string, buf: ArrayBuffer): Promise<void> {
  if (typeof caches !== 'undefined') {
    const cache = await caches.open('parquet');
    await cache.put(new Request(`https://parquet-cache/${key}`), new Response(buf, {
      headers: { 'Cache-Control': `max-age=${TTL}` }
    }));
    return;
  }
  memCache.set(key, { buf, ts: Date.now() });
}
