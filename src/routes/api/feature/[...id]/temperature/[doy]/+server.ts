import { json } from '@sveltejs/kit';
import { queryTemperatureData } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;
	
	if (!db || !r2) {
		return json({ error: 'Database or storage not available' }, { status: 500 });
	}

	const featureId = params.id;
	const doy = params.doy;
	
	// Raster bounds are now stored in D1, no need to pass from client
	const result = await queryTemperatureData(db, r2, featureId, doy);

	if (!result) {
		return json({ error: 'Temperature data not found' }, { status: 404 });
	}

	return json(result, {
		headers: {
			'cache-control': 'public, max-age=120'
		}
	});
};
