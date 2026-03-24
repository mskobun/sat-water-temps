import { queryTemperaturePointsBuffer } from '$lib/db';
import type { RequestHandler } from './$types';

/** Packed Float32 little-endian triplets: lng, lat, temperature (Kelvin). */
export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;

	if (!db || !r2) {
		return new Response('Database or storage not available', { status: 500 });
	}

	const featureId = params.id;
	const date = params.date;

	const buffer = await queryTemperaturePointsBuffer(db, r2, featureId, date);

	if (!buffer) {
		return new Response('Temperature data not found', { status: 404 });
	}

	if (buffer.byteLength === 0) {
		return new Response('No temperature points', { status: 404 });
	}

	return new Response(buffer, {
		headers: {
			'content-type': 'application/octet-stream',
			'cache-control': 'public, max-age=120'
		}
	});
};
