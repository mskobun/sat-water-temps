import type { AddProtocolAction } from 'maplibre-gl';

interface TileIndex {
	loadFn: AddProtocolAction;
	destroy: () => void;
}

const tileUrlRe = /(\d+)\/(\d+)\/(\d+)/;

/**
 * Create a Web Worker that owns geojson-vt tile indices and serves MVT tiles
 * to MapLibre via a custom protocol handler. All heavy work (GeoJSON
 * construction, geojson-vt indexing, per-tile PBF encoding) runs off the
 * main thread.
 *
 * `pointsBuffer` must be packed Float32 triplets (lng, lat, temperature).
 * It is transferred to the worker (detached); do not use it afterward.
 */
export async function createTileIndex(
	pointsBuffer: ArrayBuffer,
	pixelSizeX: number | null,
	pixelSizeY: number | null
): Promise<TileIndex> {
	const worker = new Worker(new URL('./tile-protocol.worker.ts', import.meta.url), {
		type: 'module'
	});

	// Wait for the worker to finish building the geojson-vt indices.
	await new Promise<void>((resolve, reject) => {
		worker.onmessage = (e) => {
			if (e.data.type === 'ready') resolve();
		};
		worker.onerror = (e) => reject(e);
		worker.postMessage({ type: 'init', pointsBuffer, pixelSizeX, pixelSizeY }, [pointsBuffer]);
	});

	let nextId = 0;
	const pending = new Map<number, { resolve: (buf: ArrayBuffer) => void; reject: (e: unknown) => void }>();

	worker.onmessage = (e) => {
		const msg = e.data;
		if (msg.type === 'tile') {
			const entry = pending.get(msg.id);
			if (entry) {
				pending.delete(msg.id);
				entry.resolve(msg.buffer);
			}
		}
	};

	const loadFn: AddProtocolAction = (params, abortController) => {
		const match = params.url.match(tileUrlRe);
		if (!match) {
			return Promise.reject(new Error(`Invalid tile URL: ${params.url}`));
		}

		const z = +match[1];
		const x = +match[2];
		const y = +match[3];
		const id = nextId++;

		return new Promise<{ data: ArrayBuffer }>((resolve, reject) => {
			if (abortController.signal.aborted) {
				reject(new DOMException('Aborted', 'AbortError'));
				return;
			}

			const onAbort = () => {
				pending.delete(id);
				reject(new DOMException('Aborted', 'AbortError'));
			};
			abortController.signal.addEventListener('abort', onAbort, { once: true });

			pending.set(id, {
				resolve: (buffer) => {
					abortController.signal.removeEventListener('abort', onAbort);
					resolve({ data: buffer });
				},
				reject: (err) => {
					abortController.signal.removeEventListener('abort', onAbort);
					reject(err);
				}
			});
			worker.postMessage({ type: 'getTile', id, z, x, y });
		});
	};

	function destroy() {
		// Don't actively reject pending promises — MapLibre retries any tile that
		// immediately rejects, causing an infinite error loop. Instead, let the
		// promises hang. When Svelte unmounts the VectorTileSource (because
		// tileLoadFn was set to null in the same state flush), MapLibre calls
		// abort() on every in-flight tile via its AbortController, which triggers
		// our onAbort listener and rejects with AbortError silently.
		pending.clear();
		worker.terminate();
	}

	return { loadFn, destroy };
}
