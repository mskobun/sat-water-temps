import { getParquetPaths } from '$lib/db';
import type { RequestHandler } from './$types';

/**
 * Without ?path= → returns JSON array of { path, size } for available parquet files.
 * With ?path= :
 *   HEAD → content-length only (for asyncBufferFromUrl byteLength)
 *   GET  → streams Parquet file from R2 (supports Range header for partial reads)
 */

async function handleParquetFile(
	r2: any,
	path: string,
	request: Request,
	method: 'GET' | 'HEAD'
): Promise<Response> {
	if (method === 'HEAD') {
		const head = await r2.head(path);
		if (!head) {
			return new Response(null, { status: 404 });
		}
		return new Response(null, {
			headers: {
				'content-length': String(head.size),
				'accept-ranges': 'bytes',
				'cache-control': 'public, max-age=300'
			}
		});
	}

	// GET — check for Range header
	const rangeHeader = request.headers.get('range');
	if (rangeHeader) {
		const obj = await r2.get(path, { range: { suffix: undefined, ...parseRangeHeader(rangeHeader) } });
		if (!obj) {
			return new Response('Parquet file not found in storage', { status: 404 });
		}

		const size = obj.size;
		const { start, end } = parseRangeHeader(rangeHeader);
		const contentLength = (end !== undefined ? end : size) - start;

		return new Response(obj.body as ReadableStream, {
			status: 206,
			headers: {
				'content-type': 'application/octet-stream',
				'content-range': `bytes ${start}-${(end !== undefined ? end : size) - 1}/${size}`,
				'content-length': String(contentLength),
				'accept-ranges': 'bytes',
				'cache-control': 'public, max-age=300'
			}
		});
	}

	// Full file
	const obj = await r2.get(path);
	if (!obj) {
		return new Response('Parquet file not found in storage', { status: 404 });
	}

	return new Response(obj.body as ReadableStream, {
		headers: {
			'content-type': 'application/octet-stream',
			'content-length': String(obj.size),
			'accept-ranges': 'bytes',
			'cache-control': 'public, max-age=300'
		}
	});
}

/** Parse HTTP Range header → R2-compatible range object */
function parseRangeHeader(range: string): { offset: number; length?: number; start: number; end?: number } {
	// "bytes=start-end" or "bytes=start-"
	const match = range.match(/bytes=(\d+)-(\d*)/);
	if (!match) {
		return { offset: 0, start: 0 };
	}
	const start = parseInt(match[1], 10);
	const end = match[2] ? parseInt(match[2], 10) + 1 : undefined; // R2 end is exclusive
	return {
		offset: start,
		length: end !== undefined ? end - start : undefined,
		start,
		end
	};
}

export const GET: RequestHandler = async ({ params, url, platform, request }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;

	if (!db || !r2) {
		return new Response('Database or storage not available', { status: 500 });
	}

	const featureId = params.id;
	const path = url.searchParams.get('path');

	if (!path) {
		// List available parquet files with sizes
		const paths = await getParquetPaths(db, featureId);
		const entries = await Promise.all(
			paths.map(async (p) => {
				const head = await r2.head(p);
				return { path: p, size: head?.size ?? 0 };
			})
		);
		return new Response(JSON.stringify(entries), {
			headers: {
				'content-type': 'application/json',
				'cache-control': 'public, max-age=300'
			}
		});
	}

	return handleParquetFile(r2, path, request, 'GET');
};

export const HEAD: RequestHandler = async ({ params, url, platform, request }) => {
	const r2 = platform?.env?.R2_DATA;

	if (!r2) {
		return new Response(null, { status: 500 });
	}

	const path = url.searchParams.get('path');
	if (!path) {
		return new Response(null, { status: 400 });
	}

	return handleParquetFile(r2, path, request, 'HEAD');
};
