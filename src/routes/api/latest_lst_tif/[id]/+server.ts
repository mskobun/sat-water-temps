import { getLatestDate, buildFeaturePath } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;

	if (!db || !r2) {
		return new Response('Service unavailable', { status: 500 });
	}

	const featureId = params.id;

	// Get latest date from D1
	const latestDate = await getLatestDate(db, featureId);
	if (!latestDate) {
		return new Response('Not found', { status: 404 });
	}

	// Extract name and location from featureId (format: "name/location" or just "name")
	const [name, location = 'lake'] = featureId.split('/');
	const pngKey = buildFeaturePath(featureId, `${name}_${location}_${latestDate}_filter_relative.png`);

	const obj = await r2.get(pngKey);
	if (!obj) {
		return new Response('Not found', { status: 404 });
	}

	return new Response(obj.body, {
		headers: {
			'content-type': 'image/png',
			'cache-control': 'public, max-age=300'
		}
	});
};

